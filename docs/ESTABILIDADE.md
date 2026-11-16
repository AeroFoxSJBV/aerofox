# Estabilidade e link público (gratuito)

Este documento explica como manter o AeroFox acessível aos jurados. O modelo continua independente: llama.cpp com pesos abertos Qwen, rodando na máquina da equipe. Nenhum serviço pago e nenhuma API comercial são usados.

## 1. O que roda e quem vigia

```
START_AEROFOX_PUBLICO.bat
  └─ scripts/supervisor.py   (verifica tudo a cada 10 s; reinicia só o que caiu: 5 s, 10 s, 20 s ... até 5 min)
       ├─ modelo local  llama.cpp  127.0.0.1:8793 (CPU) ou :8796 (GPU)   ← nunca publicado
       ├─ aplicação     uvicorn    127.0.0.1:8012                        ← única porta publicada
       └─ túnel         cloudflared (Quick ou Named) ou Tailscale Funnel
```

- **Modelo:** é reiniciado se o processo morrer ou se `/v1/models` falhar 3 vezes seguidas. Ele tem até 5 min para carregar.
- **Aplicação:** é reiniciada se o processo morrer ou se `/api/health` falhar 3 vezes. As conversas ficam salvas em `var/sessions.sqlite3` e voltam após o reinício.
- **Túnel:** a saúde é verificada pelo próprio link público. Um Quick Tunnel ganha um endereço **novo** quando reinicia, então ele só é reiniciado se o processo morrer ou se o link falhar por cerca de 10 minutos. O cloudflared se reconecta sozinho em quedas curtas.
- **Supervisor:** se o próprio supervisor cair, o `.bat` o reinicia após 10 s.
- **Windows:** o supervisor impede a suspensão enquanto roda. A tela pode apagar normalmente.

Arquivos em `logs/`:

| Arquivo | Conteúdo |
| --- | --- |
| `status.json` | estado atual de cada parte, número de reinícios e link público |
| `public_url.txt` | o link público atual |
| `supervisor.log` | tudo que o vigia fez (início, falhas, reinícios) |
| `app.log` | erros da aplicação (sem o texto das perguntas) |
| `llama-server.log` | o que o modelo registrou (antes isso era descartado) |
| `cloudflared.log` | mensagens do túnel |

`/api/health` mostra quantas respostas vieram do modelo e quantas do motor offline, e por quê. Exemplo: `"service": {"turns": 40, "llm_answers": 38, "offline_answers": 2, "offline_reasons": {"busy": 2}}`.

## 2. Escolha do link

| Opção | Endereço | Custo | Quando usar |
| --- | --- | --- | --- |
| Cloudflare Quick Tunnel (padrão) | `https://<aleatório>.trycloudflare.com`, muda se o túnel reiniciar | grátis, sem conta | testes e uso rápido |
| **Tailscale Funnel (recomendado para os jurados)** | `https://<computador>.<rede>.ts.net`, **fixo** | grátis (plano Personal) | link que vai no formulário da Space Apps |
| Cloudflare Named Tunnel | seu domínio, fixo | grátis **se** a equipe já tem um domínio na Cloudflare | só se já houver domínio |

### Tailscale Funnel (link fixo e gratuito)

1. Instale o Tailscale para Windows em <https://tailscale.com/download> e entre com uma conta Google, Microsoft ou GitHub.
2. No painel do Tailscale (<https://login.tailscale.com/admin>), em **DNS**, ative **MagicDNS** e **HTTPS Certificates**.
3. Num PowerShell, rode `tailscale funnel 8012` uma vez. Se o Funnel ainda não estiver liberado, o comando mostra um link para ativá-lo. Ative e feche com Ctrl+C.
4. Crie (ou edite) o arquivo `.env` na pasta do AeroFox com a linha:
   ```
   AEROFOX_TUNNEL=tailscale
   ```
5. Abra `START_AEROFOX_PUBLICO.bat`. O link aparece como `PUBLIC LINK (fixed)`. Ele é sempre o mesmo, inclusive depois de reiniciar o PC.

O Funnel publica apenas a porta 8012. O modelo e o restante da rede continuam privados.

### Cloudflare Named Tunnel (apenas se já houver domínio)

1. Em Cloudflare Zero Trust, vá em **Networks → Tunnels → Create tunnel** e escolha o tipo cloudflared.
2. Em **Public hostname**, aponte o seu subdomínio para `http://127.0.0.1:8012`.
3. Copie o token e coloque no `.env`. Esse arquivo nunca vai para o Git. Não envie o token a ninguém.
   ```
   AEROFOX_TUNNEL=cloudflare-named
   CLOUDFLARE_TUNNEL_TOKEN=<token>
   AEROFOX_PUBLIC_URL=https://aerofox.seudominio.org
   ```
   O supervisor passa o token ao cloudflared por variável de ambiente. Ele não aparece em logs nem na linha de comando.

## 3. Por que o link não cai mais com respostas longas

Antes, o navegador esperava a resposta inteira numa única requisição. Se o modelo demorasse mais de cerca de 100 s, o Cloudflare cortava a conexão com o erro 524.

Agora o navegador **inicia um trabalho** (`POST /api/chat/jobs`) e **consulta o progresso a cada segundo** (`GET /api/chat/jobs/<id>`). Nenhuma requisição dura mais que alguns milissegundos, e o visitante vê o andamento:

- "Na fila: posição 2 · ~1 min"
- "Planejando a análise…"
- "Rodando: flex035_case_study…"
- "Escrevendo a explicação…"
- um contador de segundos

A rota antiga `/api/chat` continua existindo para scripts e testes.

## 4. Vários jurados ao mesmo tempo

O modelo gera uma resposta por vez, porque um PC comum não tem memória para duas. Antes, quem esperava mais de 25 s caía no motor offline, e a terceira pessoa era recusada na hora.

Agora:

- até **6 pessoas** esperam na fila (`AEROFOX_LLM_MAX_WAITING`), cada uma vendo sua posição e uma estimativa de tempo;
- a espera vai até **240 s** (`AEROFOX_LLM_QUEUE_WAIT`);
- o turno inteiro pode levar até **300 s** (`AEROFOX_TURN_DEADLINE`).

O motor offline só entra se a fila estiver cheia ou se o tempo esgotar, e o motivo fica registrado.

O limite por visitante é de 12 mensagens por minuto (`AEROFOX_RATE_PER_MINUTE`). Com Quick Tunnel cada jurado é contado separadamente. Com Tailscale Funnel o endereço do visitante pode não ser repassado, e então todos dividem o mesmo limite. Nesse caso, use `AEROFOX_RATE_PER_MINUTE=60` no `.env` durante a avaliação.

## 5. Antes e durante a avaliação

- **Energia e rede:** use o PC na tomada, com cabo de rede se possível. Em Configurações → Sistema → Energia, defina "Suspender: Nunca".
- **Atualizações:** em Windows Update, use "Pausar atualizações" durante a semana de avaliação, para evitar reinício automático.
- **Início automático (opcional):** rode `powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1`. Ele pergunta antes de criar a tarefa, e o AeroFox passa a abrir sozinho quando você entrar no Windows. Para desfazer, use `-Remove`.
  - Para sobreviver a um reinício sem ninguém por perto, ative o login automático do Windows. Avalie se isso é aceitável para o seu PC.
- **Monitoramento gratuito:** crie um monitor HTTP(s) no UptimeRobot (plano Free, a cada 5 min) para `https://<seu-link>/api/health`, com alerta por e-mail. Você fica sabendo de uma queda antes do jurado.
- **Teste de carga real, pelo link público:**
  ```
  .venv\Scripts\python.exe scripts\soak_test.py --base https://<seu-link> --judges 3
  ```
  O resultado esperado é que todas as respostas tenham `mode: "llm"`.
- **Teste de caos:** com o AeroFox no ar, feche o processo `llama-server.exe` no Gerenciador de Tarefas. Em até cerca de 1 min, `logs\supervisor.log` deve mostrar o reinício. Faça o mesmo com o processo Python da aplicação.
- **Plano B:** coloque também o link da vitrine estática e o vídeo de demonstração no formulário. Assim o jurado vê o AeroFox funcionando mesmo se o PC estiver desligado.

  A vitrine é a interface real reproduzindo respostas reais já gravadas do modelo local, na pasta `showcase/`. Ela exibe um aviso claro de que é uma gravação.

  Para gravar de novo com o seu modelo, rode com o AeroFox no ar:
  ```
  .venv\Scripts\python.exe scripts\build_showcase.py --base http://127.0.0.1:8012
  ```

  Para publicar de graça no GitHub Pages:
  1. Crie um repositório público, por exemplo `aerofox-showcase`.
  2. Envie o **conteúdo** da pasta `showcase/` para ele.
  3. Em **Settings → Pages**, escolha "Deploy from a branch", `main`, `/ (root)`.

  O link fica `https://SEU-USUARIO.github.io/aerofox-showcase/`.

## 6. Servidor gratuito na nuvem (Oracle Cloud Always Free)

`deploy/oracle/setup.sh` prepara uma VM Ampere A1 (até 4 núcleos ARM e 24 GB, Ubuntu).

O que o script faz:

- compila o **mesmo** llama.cpp b8230 a partir do código-fonte;
- baixa os **mesmos** pesos, conferidos por SHA-256;
- cria o serviço `aerofox` no systemd, que reinicia sozinho e sobe junto com a máquina;
- usa Tailscale Funnel para o link fixo.

O Oracle pede um cartão apenas para verificação. O nível Always Free não cobra, mas confira se a conta ficou como "Always Free" e não crie recursos pagos.

**O script ainda não foi testado numa VM real pela equipe.** Teste-o com antecedência e mantenha o PC como reserva.
