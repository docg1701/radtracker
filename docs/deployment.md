# Guia de Deploy — radtracker v1.1.0

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
│   ├── all.yml                  # Placeholders genéricos (commitado)
│   ├── secrets.yml              # Credenciais reais (VAULT, NÃO commitado)
│   └── secrets.yml.example      # Template de secrets
├── templates/
│   ├── Caddyfile.j2             # Template do Caddy (LAN ou internet)
│   └── .env.j2                  # Template do .env ($ → $$)
└── playbooks/
    ├── deploy.yml               # Bootstrap + deploy idempotente
    ├── update.yml               # Atualização sem perda de dados
    ├── health.yml               # Verificação de saúde
    ├── backup.yml               # Backup do SQLite
    └── cleanup.yml              # Limpeza (preserva data/)
```

## 1. Configuração única

### 1.1 Secrets (Ansible Vault)

```bash
cp ansible/group_vars/secrets.yml.example ansible/group_vars/secrets.yml
ansible-vault encrypt ansible/group_vars/secrets.yml   # define uma senha forte
ansible-vault decrypt ansible/group_vars/secrets.yml   # pra editar depois
```

Conteúdo do `secrets.yml`:

```yaml
---
deployment_mode: lan          # ou "internet"
basicauth_users: "usuario $2a$14$HASH_GERADO_COM_CADDY"
```

### 1.2 Gerar hash da senha

```bash
docker run --rm caddy:2.9-alpine caddy hash-password --plaintext "suasenha"
# Exemplo de saída: $2a$14$DMUrdcPgJtAUJ8qo...
```

### 1.3 Modo internet — domínio

No `secrets.yml`:

```yaml
deployment_mode: internet
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
1. Instala pacotes base (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`)
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
- Caddy servindo: `http://localhost/` → 401 (BasicAuth ativo)
- fail2ban: active

## 4. Acesso

**Modo LAN:**
```
http://10.10.10.209
```

**Modo internet:**
```
https://radtracker.exemplo.com
```

Autenticação: HTTP Basic Auth (usuário e senha configurados no `secrets.yml`).

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
- Prune Docker (imagens, networks, cache)
- Remove jail do fail2ban
- `apt autoremove`

**O diretório `data/` é preservado.** O banco de dados sobrevive à limpeza.

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
docker run --rm caddy:2.9-alpine caddy hash-password --plaintext "novasenha"

# Editar secrets.yml
ansible-vault decrypt ansible/group_vars/secrets.yml
# atualizar basicauth_users
ansible-vault encrypt ansible/group_vars/secrets.yml

# Re-deployar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --ask-vault-pass
```
