# Guia de Deploy — radtracker v1.1.1

## Pré-requisitos

- VPS com **Debian 12+ ou Ubuntu 22.04+** limpo
- Acesso SSH como usuário regular com `sudo`
- Chave SSH carregada no agente (`ssh-add -l`)
- Domínio com DNS tipo A apontando pro IP do VPS (modo internet)
- IP ou hostname acessível na rede local (modo LAN)

## Estrutura de arquivos

```
ansible/
├── ansible.cfg                  # ForwardAgent, pipelining
├── inventory.yml                # VPS_HOST + VPS_USER via env vars
├── requirements.yml             # community.docker collection
├── group_vars/
│   └── all.yml                  # Variáveis compartilhadas (valores sensíveis criptografados com Vault)
├── templates/
│   ├── Caddyfile.j2             # Template do Caddy (LAN ou internet)
│   └── .env.j2                  # Template do .env ($ → $$)
└── playbooks/
    ├── deploy.yml               # Bootstrap + deploy idempotente
    ├── update.yml               # Atualização sem perda de dados
    ├── health.yml               # Verificação de saúde
    ├── backup.yml               # Backup do SQLite
    └── cleanup.yml              # Reset total do VPS
```

## 1. Configuração única

### 1.1 Secrets (Ansible Vault encrypt_string)

Valores sensíveis (`deployment_mode`, `basicauth_users`) são criptografados diretamente no `all.yml` usando `ansible-vault encrypt_string`:

```bash
# Criptografar um valor
ansible-vault encrypt_string "lan" --name deployment_mode
# Copiar o output (!vault | ...) e colar no all.yml

ansible-vault encrypt_string "galvani \$2a\$14\$HASH_AQUI" --name basicauth_users
# Copiar o output e colar no all.yml
```

O arquivo `all.yml` fica assim (valores sensíveis criptografados, resto em plaintext):

```yaml
---
radtracker_dir: "/home/{{ ansible_user }}/radtracker"
deployment_mode: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
basicauth_users: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
```

**Nota:** O arquivo `all.yml` pode ser commitado — apenas os valores marcados com `!vault` estão criptografados.

Para editar valores criptografados:
```bash
ansible-vault decrypt_string --vault-id @prompt  # ou usar --vault-password-file
```

### 1.2 Gerar hash da senha

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext "suasenha"
# Exemplo de saída: $2a$14$DMUrdcPgJtAUJ8qo...
```

### 1.3 Modo internet — domínio

No `all.yml`, edite o valor criptografado de `deployment_mode`:

```yaml
deployment_mode: !vault | ...  # valor criptografado = "internet"
```

E editar `all.yml`:

```yaml
domain: radtracker.exemplo.com
```

### 1.4 Ambiente

```bash
export VPS_HOST=10.10.10.209        # IP do VPS
export VPS_USER=galvani             # usuário SSH
```

## 2. Deploy inicial

```bash
# Instalar collection (uma vez)
ansible-galaxy collection install -r ansible/requirements.yml

# Deployar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --ask-vault-pass
```

O playbook executa em ordem:
1. Instala pacotes base (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)
2. Adiciona repositório Docker (Ubuntu ou Debian, detectado automaticamente)
3. Instala Docker Engine + Compose plugin
4. Clona repositório privado via SSH agent forwarding
5. Cria diretórios persistentes (`data/`, `backups/`, `caddy_logs/`)
6. Gera `Caddyfile` e `.env` a partir dos templates
7. Ajusta permissões (`chown 1000:1000` no `data/`)
8. Instala e configura fail2ban (filtro de 401, jail, cria `access.log`)
9. Builda imagem e sobe containers (`docker compose up --build`)
10. Aguarda health check do Streamlit

**O deploy é idempotente** — seguro rodar quantas vezes quiser.

## 3. Verificação

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --ask-vault-pass
```

Verifica:
- Container `radtracker`: existe, running, healthy
- Endpoint Streamlit: `/_stcore/health` → 200
- Container `caddy`: existe, running
- Caddy servindo: `https://localhost/` → 401 (BasicAuth ativo)
- fail2ban: active

## 4. Acesso

**Modo LAN:**
```
https://10.10.10.209
```
(HTTPS com certificado autoassinado — aceitar aviso de segurança no primeiro acesso)

**Modo internet:**
```
https://radtracker.exemplo.com
```

Autenticação: HTTP Basic Auth (usuário e senha configurados no `all.yml`, valor `basicauth_users` criptografado).

## 5. Atualização

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml --ask-vault-pass
```

- Faz `git fetch` + `reset --hard` (só toca arquivos trackeados)
- Regenera `Caddyfile` e `.env`
- Rebuilda imagem e recria container
- Aguarda health check

**Dados preservados:** O bind mount `data/` não é tocado. SQLite sobrevive a updates.

## 6. Backup

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --ask-vault-pass
```

- Cria `.backup` dentro do container com `sqlite3`
- Copia pro host em `backups/`
- Verifica integridade com `PRAGMA integrity_check`
- Rotaciona backups antigos (>30 dias)

## 7. Limpeza

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/cleanup.yml --ask-vault-pass
```

- Para e remove containers
- Prune Docker (imagens, volumes, networks, build cache)
- Remove Docker (pacotes, GPG key, repositório APT)
- Remove fail2ban (jail, filter, pacote)
- Remove diretório do projeto
- Remove pré-requisitos (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)
- `apt autoremove` + `apt autoclean`

VPS volta ao estado original — pronto pra um novo bootstrap + deploy.

Remove radtracker, Docker, fail2ban e todos os pré-requisitos instalados. VPS volta ao estado original.

## Solução de problemas

### SSH agent não funciona

```bash
ssh-add -l                     # verificar se chave está carregada
ssh-add ~/.ssh/id_ed25519      # carregar se necessário
ssh -o ForwardAgent=yes galvani@VPS 'ssh -T git@github.com'  # testar forward
```

### fail2ban não inicia

```bash
sudo tail -50 /var/log/fail2ban.log
# "Have not found any log file" → rodar deploy.yml de novo (cria access.log)
# ou manualmente: sudo touch /home/galvani/radtracker/caddy_logs/access.log
```

### Docker não instala (Debian)

O playbook usa `signed-by=/etc/apt/keyrings/docker.asc` (método moderno).
Funciona em Debian 12+ e Ubuntu 22.04+. Sem dependência de `apt-key` (removido no Debian 13).

### Porta 80/443 em uso

```bash
sudo lsof -i :80
sudo lsof -i :443
sudo systemctl stop nginx apache2   # parar servidores conflitantes
```

### Let's Encrypt falha (modo internet)

- Verificar DNS: `dig +short radtracker.exemplo.com` deve retornar o IP do VPS
- Aguardar propagação (1–10 minutos)
- Testar com staging CA antes de produção:
  ```caddy
  tls {
      ca https://acme-staging-v02.api.letsencrypt.org/directory
  }
  ```

### Senha errada / reset de senha

```bash
# Gerar novo hash
docker run --rm caddy:2-alpine caddy hash-password --plaintext "novasenha"

# Editar all.yml — criptografar novo valor
ansible-vault encrypt_string "galvani \$2a\$14\$NOVO_HASH" --name basicauth_users
# Substituir o bloco !vault existente no all.yml pelo novo output

# Re-deployar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --ask-vault-pass
```
