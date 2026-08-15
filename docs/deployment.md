# Guia de Deploy — radtracker

## Pré-requisitos

- VPS com **Debian 12+ ou Ubuntu 22.04+** limpo
- Acesso SSH como usuário regular com `sudo`
- Token de acesso GitHub (Personal Access Token classic) com escopo `repo`
- Domínio com DNS tipo A apontando pro IP do VPS (modo internet)
- IP ou hostname acessível na rede local (modo LAN)

## Estrutura de arquivos

```text
ansible/
├── ansible.cfg                  # Pipelining, host key check disabled
├── inventory.yml                # VPS_HOST + VPS_USER via env vars
├── requirements.yml             # community.docker + community.crypto collections
├── group_vars/
│   └── all.yml                  # Variáveis compartilhadas (valores sensíveis criptografados com Vault)
├── templates/
│   ├── Caddyfile.j2             # Template do Caddy (LAN ou internet)
│   └── .env.j2                  # Template do .env (DOMAIN + TZ)
└── playbooks/
    ├── deploy.yml               # Bootstrap + deploy idempotente
    ├── update.yml               # Atualização sem perda de dados
    ├── health.yml               # Verificação de saúde
    ├── backup.yml               # Backup do SQLite
    └── cleanup.yml              # Reset total do VPS
```

## 1. Configuração única

### 1.1 Secrets (Ansible Vault encrypt_string)

Valores sensíveis (`deployment_mode`, `auth_username`, `auth_password`,
`github_pat`) são criptografados diretamente no `all.yml` usando
`ansible-vault encrypt_string`:

```bash
# Criptografar um valor (o arquivo de senha do vault está em ansible/.vault_pass)
printf '%s' "lan" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name deployment_mode

printf '%s' "galvani" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name auth_username

printf '%s' "SENHA_DO_LOGIN_WEB" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name auth_password

printf '%s' "ghp_SEU_TOKEN_AQUI" | ansible-vault encrypt_string --vault-password-file ansible/.vault_pass --stdin-name github_pat
# Copiar cada output (!vault | ...) e colar no all.yml
```

`auth_username`/`auth_password` são as credenciais do **login web** do radtracker
(criadas no primeiro deploy pelo bootstrap — senha mínima de 8 caracteres).

O arquivo `all.yml` fica assim (valores sensíveis criptografados, resto em plaintext):

```yaml
---
radtracker_dir: "/home/{{ ansible_user }}/radtracker"
deployment_mode: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
auth_username: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
auth_password: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
github_pat: !vault |
      $ANSIBLE_VAULT;1.1;AES256
      ...
deploy_key_path: "/home/{{ ansible_user }}/.ssh/radtracker_deploy"
```

**Nota:** O arquivo `all.yml` pode ser commitado — apenas os valores marcados com `!vault` estão criptografados.

Para editar valores criptografados:

```bash
ansible-vault edit --vault-password-file ansible/.vault_pass ansible/group_vars/all.yml
```

### 1.2 Criar token de acesso GitHub (PAT)

O PAT é usado uma única vez: para registrar a chave SSH do VPS como deploy key no repositório.

1. Acesse [GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Clique **Generate new token (classic)**
3. Nome: `radtracker-deploy`
4. Expiração: conforme sua política (recomendado 90 dias)
5. Escopo: **repo** (acesso a repositórios privados + gerenciar deploy keys)
6. Copie o token gerado (ex: `ghp_xxxx`)
7. Criptografe com:

   ```bash
   ansible-vault encrypt_string "ghp_xxxx" --name github_pat
   ```

8. Substitua o bloco `github_pat: !vault |` no `all.yml` pelo output

**Nota:** Após o registro da deploy key, o PAT pode expirar sem impacto —
a autenticação git passa a usar a chave SSH.

### 1.3 Senha do login web

A senha do login web **não é hashada manualmente** — o bootstrap roda
`hashlib.scrypt` na primeira vez que o container sobe (`python -m src.auth_bootstrap`,
invocado pelo `deploy.yml`). O `auth_password` do vault é o texto plano da senha;
mínimo de 8 caracteres. Para trocá-la depois, use `radtracker-auth` opção 3 (ver §4).

### 1.4 Modo internet — domínio

No `all.yml`, edite o valor criptografado de `deployment_mode`:

```yaml
deployment_mode: !vault | ...  # valor criptografado = "internet"
```

E editar `all.yml`:

```yaml
domain: radtracker.duckdns.org
```

### 1.4.1 DuckDNS (domínio gratuito)

Se não tiver domínio próprio, use [DuckDNS](https://duckdns.org):

1. Faça login com GitHub e crie o subdomínio `radtracker`
2. Aponte o IP da instância:

   ```bash
   curl "https://www.duckdns.org/update?domains=radtracker&token=SEU_TOKEN&ip=129.151.4.89"
   ```

3. Configure renovação automática via cron (o IP da Oracle Free Tier é
   estático, mas o DuckDNS exige update periódico):

   ```cron
   0 */12 * * * curl -s "https://www.duckdns.org/update?domains=radtracker&token=SEU_TOKEN" > /dev/null
   ```

### 1.5 Ambiente

```bash
export VPS_HOST=129.151.4.89         # IP do VPS (Oracle Cloud Free Tier)
export VPS_USER=ubuntu               # usuário SSH
```

### 1.6 Arquivo de senha do Vault

Crie um arquivo com a senha do Ansible Vault (já está no `.gitignore`):

```bash
echo -n "sua_senha_vault" > ansible/.vault_pass
chmod 600 ansible/.vault_pass
```

Isso evita o prompt interativo de senha em todos os comandos abaixo.

## 2. Deploy inicial

```bash
# Instalar collections (uma vez)
ansible-galaxy collection install -r ansible/requirements.yml

# Deployar (usa --vault-password-file para evitar prompt interativo)
ansible-playbook -i ansible/inventory.yml ansible/playbooks/deploy.yml --vault-password-file ansible/.vault_pass
```

O playbook executa em ordem:

1. Instala pacotes base (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)
2. Adiciona repositório Docker (Ubuntu ou Debian, detectado automaticamente)
3. Instala Docker Engine + Compose plugin
4. Gera chave SSH ed25519 no VPS e registra como deploy key no GitHub (usa `github_pat` do Vault)
5. Cria diretórios persistentes (`data/`, `backups/`, `caddy_logs/`)
6. Busca templates do clone VPS, gera `Caddyfile` e `.env` a partir deles
7. Ajusta permissões (`chown 1000:1000` no `data/`)
8. Instala e configura fail2ban (whitelist de redes locais + jail sshd)
9. Builda imagem e sobe containers (`docker compose up --build`)
10. Aguarda health check do Streamlit
11. Roda o bootstrap de autenticação no container (cria `data/auth.json` a
    partir das credenciais do vault)
12. Instala o wrapper SSH `/usr/local/bin/radtracker-auth`
13. Imprime o endereço de acesso + lembrete para ativar a 2FA

**O deploy é idempotente** — seguro rodar quantas vezes quiser. O bootstrap
**não sobrescreve** um `auth.json` existente (troque senha/2FA via
`radtracker-auth`).

> ⚠️ **Cutover de autenticação:** este deploy remove o BasicAuth do Caddy.
> Use SEMPRE `deploy.yml` (nunca `update.yml`) na primeira execução após a mudança —
> o `update.yml` não roda o bootstrap nem cria o wrapper. Depois que `auth.json`
> existir, o `update.yml` volta a ser seguro.

## 3. Verificação

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --vault-password-file ansible/.vault_pass
```

Verifica:

- Container `radtracker`: existe, running, healthy
- Endpoint Streamlit: `/_stcore/health` → 200
- Container `caddy`: existe, running
- Caddy servindo: página de login do radtracker (não mais 401 de BasicAuth)
- fail2ban: active

## 4. Acesso

**Oracle Cloud Free Tier (produção):**

```text
https://radtracker.duckdns.org
```

(Let's Encrypt — certificado assinado, sem aviso de segurança)

Shape: VM.Standard.E2.1.Micro — 1 OCPU AMD, 1 GB RAM, 50 GB boot
Domínio: DuckDNS gratuito (radtracker.duckdns.org → 129.151.4.89)

**VPS local (LAN):**

```text
https://10.10.10.209
```

(HTTPS com certificado autoassinado — aceite o aviso de segurança no primeiro acesso;
o Caddy redireciona HTTP→HTTPS automaticamente)

**Modo internet (com domínio próprio):**

```text
https://radtracker.exemplo.com
```

### Autenticação (login web + 2FA)

O primeiro acesso pede usuário e senha (definidos no vault, §1.1). Sem 2FA, um aviso
âmbar aparece no app. Para ativar a 2FA:

```bash
ssh galvani@10.10.10.209    # (ou o host de produção)
radtracker-auth             # wrapper para o menu de gestão
# Opção 1: Ativar / reconfigurar 2FA — escaneie o QR com o celular e digite o código
```

Menu completo do `radtracker-auth`:

| Opção | Ação |
|-------|------|
| 1 | Ativar / reconfigurar 2FA (QR no terminal + URI de fallback; gera segredo NOVO a cada execução — re-escaneie o QR) |
| 2 | Desativar 2FA |
| 3 | Trocar senha (encerra todas as sessões web) |
| 4 | Trocar usuário (encerra todas as sessões web) |
| 5 | Sessão web (dias, 1–365) — trocar o valor rotaciona o segredo e encerra todas as sessões na hora |
| 6 | Reparar `auth.json` |
| 7 | Status (2FA, TOTP, sessão, arquivo — nunca exibe segredos) |

- A sessão web dura 30 dias por padrão (cookie assinado), configurável na
  opção 5; trocar a senha, o usuário ou a duração revoga todas as sessões.
- `auth.json` não entra nos backups (só `telerrad.db`) — se `data/` for
  perdido, re-inicialize com a opção 6 ou um redeploy.
- **Ative a 2FA imediatamente após cada deploy**: até lá o app depende só
  da senha, sem limite de tentativas em nível de rede.

## 5. Atualização

```bash
# VPS local (LAN) — os DOIS overrides são OBRIGATÓRIOS aqui:
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass \
  -e deployment_mode=lan -e github_branch=<branch>

# Produção (modo internet do vault) — sem override de deployment_mode:
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass -e github_branch=<branch>
```

**Fluxo de produção (Oracle), na ordem:**

```bash
# 1. Backup SEMPRE antes de atualizar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --vault-password-file ansible/.vault_pass
# copiar o backup do VPS para o repositório (gitignored):
scp ubuntu@129.151.4.89:~/radtracker/backups/radtracker-*.db backups/

# 2. Atualizar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/update.yml \
  --vault-password-file ansible/.vault_pass -e github_branch=master

# 3. Verificar
ansible-playbook -i ansible/inventory.yml ansible/playbooks/health.yml --vault-password-file ansible/.vault_pass
```

- Atualiza repositório via deploy key SSH (`git` module) no branch informado
- Regenera `Caddyfile` e `.env` a partir dos templates do clone VPS
  (sem `deployment_mode=lan`, um VPS LAN vira modo internet e o Caddy tenta ACME para o domínio de produção)
- `RADTRACKER_MODE` no `.env` segue `deployment_mode`: lan → `local`, internet → `web` (rodapé da sidebar)
- Rebuilda imagem e recria container
- Aguarda health check

**Playbook interrompido?** Re-rodar o MESMO comando — os playbooks são idempotentes
(e.g. o bootstrap de auth só cria `auth.json` se não existir). Nunca corrija o
servidor à mão; o re-run repara qualquer estado parcial.

**Dados preservados:** O bind mount `data/` não é tocado. SQLite sobrevive a updates.

## 6. Backup

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/backup.yml --vault-password-file ansible/.vault_pass
```

- Cria `.backup` dentro do container com `sqlite3`
- Copia pro host em `backups/`
- Verifica integridade com `PRAGMA integrity_check`
- Rotaciona backups antigos (>30 dias)

## 7. Limpeza

```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/cleanup.yml --vault-password-file ansible/.vault_pass
```

- Para e remove containers
- Prune Docker (imagens, volumes, networks, build cache)
- Remove Docker (pacotes, GPG key, repositório APT)
- Remove fail2ban (jail sshd, pacote)
- Remove o wrapper `/usr/local/bin/radtracker-auth`
- Remove diretório do projeto
- Remove pré-requisitos (`ca-certificates`, `curl`, `gnupg`, `git`, `sqlite3`, `python3-requests`)

## 8. Cloudflare (produção)

O domínio de produção `radtracker.drgalvanimd.com` é gerido pelo Cloudflare
(zona `drgalvanimd.com`). Esta é a única proteção de rede contra brute-force
no login — **não desligue o proxy nem remova a regra de rate limiting**.

### 8.1 Registro DNS

- Type `A`, name `radtracker`, IPv4 `129.151.4.89` (IP da Oracle), TTL Auto,
  **Proxy: Proxied** (nuvem laranja — obrigatório para o rate limiting).
- SSL/TLS da zona: **Full (strict)**. A origem (Caddy) tem certificado
  Let's Encrypt próprio emitido via HTTP-01 através do proxy; o Flexible
  quebra o fluxo (o Caddy redireciona HTTP→HTTPS em loop).

### 8.2 Rate limiting (WAF → Rate limiting rules)

Regra única para todo o login:

| Campo | Valor |
|-------|-------|
| Nome | `radtracker-login` |
| Expression | `http.host eq "radtracker.drgalvanimd.com" and http.request.method eq "POST" and http.request.uri.path eq "/"` |
| Limite | 10 requisições / 10 segundos |
| Ação | Block (10 segundos) |

> No plano Free, período e duração do block são **fixos em 10 segundos** —
> valores maiores exigem plano pago. A regra estrangula rajadas de brute
> force; tentativas espaçadas são contidas por scrypt + TOTP.

Por que essa expressão: o formulário de login e o passo TOTP do Streamlit
são os únicos `POST` em `/` — o app autenticado roda sobre um único
websocket (`GET /_stcore/stream`), que a regra não conta. Bloqueia força
bruta contra senha e código TOTP sem tocar em sessão legítima.

### 8.3 Logs atrás do proxy

O Caddy vê o IP de borda do Cloudflare (não o do cliente) — o IP real vem
no header `Cf-Connecting-Ip`. O fail2ban atual cobre só a jail sshd, então
não há impacto; se um dia houver jail HTTP, filtrar pelo header, não pelo
IP de origem da conexão.

## Solução de problemas

### Deploy key não registra no GitHub

Se o deploy falhar na tarefa "Register deploy key with GitHub":

```bash
# 1. Verificar se o github_pat está válido (não expirado)
ansible-vault view ansible/group_vars/all.yml --vault-password-file ansible/.vault_pass | grep github_pat

# 2. Testar o PAT manualmente:
curl -H "Authorization: Bearer SEU_PAT" https://api.github.com/repos/docg1701/radtracker/keys

# 3. Se o PAT expirou, gerar novo em https://github.com/settings/tokens
#    e re-criptografar:
ansible-vault encrypt_string "ghp_NOVO_TOKEN" --name github_pat
#    Substituir o bloco no all.yml

# 4. Se a chave já existe mas corrompeu, removê-la manualmente:
#    Acesse https://github.com/docg1701/radtracker/settings/keys
#    Delete "radtracker-vps-<IP>" (ou qualquer chave radtracker-vps-* obsoleta) e re-rode deploy.yml
#    Cada VPS registra sua própria chave com nome único baseado no ansible_host (o IP do VPS)

# 5. Para re-gerar a chave SSH no VPS (force):
ssh galvani@VPS "rm ~/.ssh/radtracker_deploy*"
# Re-rodar deploy.yml — a task openssh_keypair recria a chave
```

### fail2ban não inicia

```bash
sudo tail -50 /var/log/fail2ban.log
sudo fail2ban-client status sshd   # o jail ativo agora é o do sshd (journald)
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
# Conecte via SSH e use o menu de gestão:
radtracker-auth
# Opção 3: Trocar senha (mínimo 8 caracteres, encerra todas as sessões web)
# Opção 6: Reparar auth.json (se o arquivo estiver ausente/corrompido)
```

Re-rodar o `deploy.yml` **não** troca a senha — o bootstrap é idempotente e nunca
sobrescreve um `auth.json` existente.
