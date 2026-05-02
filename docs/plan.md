# Plano: Deploy Key SSH no Ansible (substitui ForwardAgent)

**Data:** 2026-05-02
**Problema:** O `git fetch`/`git clone` falha silenciosamente nos playbooks Ansible porque o `SSH_AUTH_SOCK` não é propagado em shells não-interativos, mesmo com `ForwardAgent=yes`. O repositório é privado e o usuário prefere acesso SSH.

**Solução:** Gerar uma chave SSH `ed25519` no VPS, registrá-la como deploy key no GitHub via API (usando PAT criptografado no Vault), e usar o módulo nativo `ansible.builtin.git` com `key_file`.

---

## Objetivo

Eliminar a dependência de `ssh-agent` forwarding nos playbooks `deploy.yml` e `update.yml`, substituindo por autenticação baseada em deploy key SSH gerenciada automaticamente.

---

## Tarefas (ordem de execução)

### 1. Adicionar `github_pat` criptografado ao Vault
- **Arquivo:** `ansible/group_vars/all.yml`
- **Ação:** Adicionar variável `github_pat` criptografada com `ansible-vault encrypt_string`
- **Requisito:** O PAT deve ser um token GitHub classic com escopo `repo` (para acessar repo privado e gerenciar deploy keys)
- **Idempotente:** Não se aplica (variável estática)
- **Verificação:** `ansible-vault view ansible/group_vars/all.yml` deve mostrar o valor descriptografado

### 2. Adicionar variável para caminho da deploy key
- **Arquivo:** `ansible/group_vars/all.yml`
- **Ação:** Adicionar `deploy_key_path: "/home/{{ ansible_user }}/.ssh/radtracker_deploy"`
- **Verificação:** Variável disponível nos playbooks

### 3. Gerar par de chaves SSH no VPS (idempotente)
- **Arquivo:** `ansible/playbooks/deploy.yml`
- **Ação:** Adicionar task usando `community.crypto.openssh_keypair` antes do clone:
  ```yaml
  - name: Generate deploy key for GitHub access
    community.crypto.openssh_keypair:
      path: "{{ deploy_key_path }}"
      type: ed25519
      comment: "radtracker-deploy-{{ inventory_hostname }}"
      force: false  # nunca sobrescreve chave existente
    become: false
  ```
- **Idempotente:** Sim — `force: false` preserva chave existente
- **Verificação:** Segunda execução deve retornar `ok` (não `changed`)

### 4. Registrar chave pública como deploy key no GitHub
- **Arquivo:** `ansible/playbooks/deploy.yml`
- **Ação:** Adicionar task após geração da chave:
  ```yaml
  - name: Register deploy key with GitHub
    ansible.builtin.uri:
      url: "https://api.github.com/repos/docg1701/radtracker/keys"
      method: POST
      headers:
        Authorization: "Bearer {{ github_pat }}"
        Accept: "application/vnd.github+json"
      body:
        title: "radtracker-vps"
        key: "{{ lookup('file', deploy_key_path + '.pub') }}"
        read_only: true
      body_format: json
      status_code: [201, 422]
    register: deploy_key_result
    become: false
    changed_when: deploy_key_result.status == 201
  ```
- **Tratamento de erro:** `status_code: [201, 422]` — 422 = key já existe (idempotente), 201 = criada
- **Atenção:** `lookup('file')` lê do controlador local, não do VPS. A chave pública precisa ser lida do VPS. Solução: usar `ansible.builtin.slurp` antes para ler o arquivo remoto:
  ```yaml
  - name: Read deploy public key
    ansible.builtin.slurp:
      src: "{{ deploy_key_path }}.pub"
    register: pubkey_content
    become: false
  ```
  E usar `{{ pubkey_content.content | b64decode }}` no body.

### 5. Substituir `shell: git clone/fetch` por `ansible.builtin.git` no deploy.yml
- **Arquivo:** `ansible/playbooks/deploy.yml`
- **Ação:** Remover task "Clone or reset repository" (shell) e substituir por:
  ```yaml
  - name: Clone or update repository via deploy key
    ansible.builtin.git:
      repo: "{{ github_repo }}"
      dest: "{{ radtracker_dir }}"
      version: "{{ github_branch }}"
      key_file: "{{ deploy_key_path }}"
      accept_hostkey: true
      force: yes
      update: yes
    become: false
    register: git_result
  ```
- **Vantagens:** `update: yes` + `force: yes` faz fetch+reset automaticamente, igual ao shell antigo
- **Verificação:** Deploy limpo (sem diretório) e re-deploy (com diretório existente) devem ambos funcionar

### 6. Substituir `shell: git fetch` por `ansible.builtin.git` no update.yml
- **Arquivo:** `ansible/playbooks/update.yml`
- **Ação:** Remover task "Fetch and reset" (shell) e substituir por:
  ```yaml
  - name: Update repository via deploy key
    ansible.builtin.git:
      repo: "{{ github_repo }}"
      dest: "{{ radtracker_dir }}"
      version: "{{ github_branch }}"
      key_file: "{{ deploy_key_path }}"
      accept_hostkey: true
      force: yes
      update: yes
    become: false
  ```
- **Verificação:** `git log` no VPS deve mostrar o commit mais recente após update

### 7. Limpar `ansible.cfg`
- **Arquivo:** `ansible/ansible.cfg`
- **Ação:** Remover `ssh_args = -o ForwardAgent=yes` da seção `[ssh_connection]`
- **Justificativa:** Não é mais necessário e dá falsa impressão de que funciona

### 8. Atualizar `docs/deployment.md`
- **Arquivo:** `docs/deployment.md`
- **Alterações necessárias:**
  - Seção "Pré-requisitos": remover "Chave SSH carregada no agente"
  - Seção "1.1 Secrets": adicionar instrução para criar `github_pat`
  - Seção "2. Deploy inicial": atualizar passo 4 (era "SSH agent forwarding", agora "deploy key gerada automaticamente")
  - Seção "Solução de problemas": remover seção "SSH agent não funciona", adicionar "Deploy key não registra"
  - Adicionar nota sobre como criar o PAT no GitHub (Settings → Developer settings → Personal access tokens → Tokens (classic))

---

## Ordem de dependências

```
1 (github_pat no vault)
  └─> 4 (registrar deploy key no GitHub)
        └─> 5, 6 (usar deploy key no git clone/fetch)
2 (variável deploy_key_path)
  └─> 3, 4, 5, 6
3 (gerar chave)
  └─> 4 (registrar chave)
7 (limpar ansible.cfg) — independente
8 (atualizar docs) — após tudo implementado
```

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| PAT expirado ou revogado | Documentar no deployment.md como renovar |
| Deploy key já existe com outro título | `status_code: 422` tratado como ok |
| `community.crypto.openssh_keypair` não instalado | Já deve estar disponível (parte do `community.crypto`); verificar `requirements.yml` |
| `become: false` no git module causa erro de permissão | Testar: o diretório `radtracker_dir` é owned pelo ansible_user |
| Conflito com chave SSH existente no VPS | `force: false` preserva chaves existentes; deploy key vive em arquivo separado |

---

## Validação pós-implementação

```bash
# 1. Verificar vault
ansible-vault view ansible/group_vars/all.yml --vault-password-file ansible/.vault_pass | grep github_pat

# 2. Deploy limpo
VPS_HOST=10.10.10.209 VPS_USER=galvani ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --vault-password-file ansible/.vault_pass

# 3. Verificar git log no VPS
ssh galvani@10.10.10.209 "cd ~/radtracker && git log --oneline -3"

# 4. Update
VPS_HOST=10.10.10.209 VPS_USER=galvani ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml --vault-password-file ansible/.vault_pass

# 5. Verificar que update trouxe código novo
ssh galvani@10.10.10.209 "cd ~/radtracker && git log --oneline -3"

# 6. Idempotência: rodar deploy.yml de novo, deve retornar 0 changed
```
