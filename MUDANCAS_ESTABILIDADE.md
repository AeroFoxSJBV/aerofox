# AeroFox 1.1.2: o que mudou para a estabilidade

Esta versão parte da 1.1.1 entregue pelo Codex. O objetivo foi um só: **o link não cair quando os jurados acessarem**.

O que **não** mudou:

- **Modelo:** o mesmo, independente e de pesos abertos. Qwen2.5-1.5B no perfil CPU e Qwen3-4B no perfil GPU, rodando no seu computador via llama.cpp b8230, com os mesmos arquivos e os mesmos hashes SHA-256.
- **Serviços:** nenhuma API comercial e nenhum serviço pago.
- **Lógica científica:** as ferramentas, os dados da NASA, os prompts e o plano do agente estão iguais.
- **Interface:** a identidade visual está igual.

## 1. Por que caía, e o que foi feito

| Problema na 1.1.1 | Consequência | Correção na 1.1.2 |
| --- | --- | --- |
| A resposta ia numa única requisição, que podia levar mais de 100 s | O Cloudflare corta conexões longas (erro 524) e o jurado via "erro" | **Trabalho + consulta de progresso.** O navegador inicia a resposta e pergunta "já terminou?" a cada segundo. Cada requisição leva milissegundos. |
| A fila do modelo aceitava 2 pessoas esperando, por no máximo 25 s | O 2º ou 3º jurado simultâneo recebia a resposta do motor offline, mais pobre | **Fila visível** de até 6 pessoas, com espera de até 240 s. Cada jurado vê "posição 2, ~1 min". |
| Nada vigiava os processos. O modelo rodava com `--log-disable` e sem janela | Se o modelo travasse, ninguém percebia. O link ficava no ar mostrando só o motor offline. | **Supervisor** (`scripts/supervisor.py`). A cada 10 s ele confere o modelo, a aplicação e o túnel, e reinicia só a parte que caiu. Tudo fica registrado em `logs/`. |
| O link `trycloudflare.com` mudava a cada execução | Um link enviado no formulário deixava de valer | **Link fixo gratuito via Tailscale Funnel.** Uma linha no `.env`. O Quick Tunnel só é reiniciado se morrer de fato. |
| As conversas ficavam só na memória | Um reinício apagava a conversa do jurado | Conversas salvas em **SQLite** (`var/sessions.sqlite3`). Voltam após reinício e expiram em 6 h. |
| O modelo pequeno às vezes respondia só com títulos (`**Evidence:**`) e citações | O jurado via uma resposta vazia | **Guarda contra respostas vazias.** Uma resposta com só títulos e citações é rejeitada. O sistema refaz a resposta curta e, se ainda falhar, mostra a análise verificada. Respostas normais **não são alteradas**: os títulos continuam lá. |
| O PC podia dormir | O link caía | O supervisor impede a suspensão do Windows enquanto roda. |
| Não havia como saber quantas vezes o modelo falhou | Problemas apareciam só quando o jurado reclamava | `/api/health` mostra respostas do modelo, respostas offline e o **motivo** de cada fallback. |

## 2. Arquivos alterados e criados

**Backend (inferência e API)**

- `backend/aerofox/agent/progress.py` (novo):
  - eventos de progresso (fila, planejamento, ferramentas, escrita);
  - contadores de serviço.
- `backend/aerofox/agent/llm.py`:
  - fila com posição e estimativa de tempo;
  - aviso de etapa;
  - filtro de respostas só com títulos.

  O prompt, o plano por gramática, as ferramentas e a regra de "sem números inventados" **não mudaram**.
- `backend/aerofox/config.py`: novos prazos padrão.
  - modelo: 65 → 120 s;
  - espera na fila: 25 → 240 s;
  - turno: 100 → 300 s.
- `backend/aerofox/agent/state.py` e `orchestrator.py`:
  - sessões persistidas em SQLite;
  - contadores por resposta.
- `backend/aerofox/api/app.py`:
  - `POST /api/chat/jobs` e `GET /api/chat/jobs/{id}`;
  - `/api/health` com os contadores e a fila.

  `/api/chat` continua existindo.

**Interface**

- `frontend/app.js` e `styles.css`:
  - usam o novo fluxo de trabalho com consulta de progresso;
  - mostram a etapa, a posição na fila e um contador de segundos.

  Fora isso, a interface está igual.

**Execução e publicação**

- `scripts/supervisor.py` (novo): o vigia com reinício automático.
  - **Proteção do token:** o token do túnel nomeado é passado só por variável de ambiente.
  - **Porta publicada:** apenas a do AeroFox.
- `START_AEROFOX_PUBLICO.bat`: reescrito para usar o supervisor. Ainda pergunta antes de instalar o `cloudflared`.
- `scripts/install_autostart.ps1` (novo, opcional): inicia o AeroFox ao entrar no Windows. Pede confirmação.
- `scripts/local_model.py`:
  - o llama.cpp passa a gravar log em `logs/llama-server.log`;
  - o modelo tem até 5 min para carregar (antes, 1 min).
- `scripts/launch.py`: nova opção `--setup-only`, usada pelo `.bat`.
- `deploy/oracle/setup.sh` (novo, **não testado numa VM real**): servidor gratuito Oracle Always Free com o mesmo llama.cpp e os mesmos pesos, como serviço `systemd`.

**Testes e verificação**

- `tests/test_stability.py` (novo): 15 testes.
- `scripts/soak_test.py` (novo): simula vários jurados ao mesmo tempo, pelo caminho que o navegador usa.
- `scripts/build_showcase.py` e `scripts/showcase_replay.js` (novos): geram a **vitrine estática**.
  - É a interface real reproduzindo respostas reais gravadas do modelo local.
  - Pode ser hospedada de graça no GitHub Pages, como link reserva para os jurados.

**Documentação**

- `docs/ESTABILIDADE.md` (novo): passo a passo do link fixo, monitoramento gratuito, testes de caos e de carga, e Oracle.
- `GUIA_COMPARTILHAR_AEROFOX.md`, `docs/DEPLOYMENT.md` e `.env.example`: atualizados.

## 3. Como verifiquei

Todos os testes abaixo rodaram com o **modelo real** (Qwen2.5-1.5B, o mesmo arquivo do perfil CPU). Foram feitos num servidor Linux de 4 núcleos, não no seu PC. Os números completos estão em `reports/stability_comparison_1.1.2.json`.

**Qualidade: a mesma, com uma melhora.** Fiz as mesmas 11 perguntas à versão 1.1.1 original e à 1.1.2. São perguntas em inglês e português, com acompanhamento ("E em Marte?", "Explique de forma mais simples"), revisão de projeto, histórico e conceito.

| Medida | 1.1.1 | 1.1.2 |
| --- | --- | --- |
| Respostas escritas pelo modelo local | 11/11 | 11/11 |
| Mesmo plano, mesmas ferramentas, mesmos gráficos e mesmas fontes | — | 11/11 |
| Texto **idêntico, palavra por palavra** | — | 10/11 |
| Resposta vazia (só um título e citações) | 1 (Saffire-II: 8 palavras) | 0 (a mesma pergunta virou uma explicação real de 29 palavras) |
| Tempo mediano por resposta | 37 s | 41 s (a diferença vem da nova tentativa na pergunta do Saffire) |

Na primeira versão da guarda contra respostas vazias, o teste mostrou que ela apagava os títulos em negrito de respostas boas, o que piorava 3 respostas. Corrigi isso antes de entregar. A guarda agora só age quando a resposta não tem conteúdo nenhum. O resultado da tabela é o da versão corrigida.

**Três jurados ao mesmo tempo:**

| | 1.1.1 | 1.1.2 |
| --- | --- | --- |
| Respostas do modelo | 1/3. Os outros 2 caíram no motor offline após 25 s, motivo "busy". | **3/3**, em 25 s, 67 s e 95 s, com a posição na fila visível |

**Testes automáticos:**

- **Testes Python:** 74/74 passaram, sendo 59 antigos e 15 novos (`tests/test_stability.py`).
- **Teste de navegador:** 25/25 verificações passaram com o novo fluxo de progresso. Os cartões, gráficos, CSV, gavetas, a biblioteca, o celular e o português continuam funcionando.

**Supervisor:** derrubei a aplicação de propósito com `kill -9`. O supervisor detectou e ela voltou sozinha em cerca de 20 s.

**Vitrine estática:** tem 9 respostas reais gravadas. Testei no navegador as perguntas, o acompanhamento, a gaveta de fontes, o download de CSV, o aviso para perguntas não gravadas e a ausência de erros no console.

**O que NÃO pude testar daqui, porque este ambiente não acessa o seu PC nem a rede do Cloudflare:**

- o `.bat` no Windows;
- o túnel real (Cloudflare ou Tailscale);
- o perfil GPU (Qwen3-4B);
- a instalação na Oracle.

O passo 4 abaixo é exatamente esse teste, no seu PC.

## 4. O que você precisa fazer no seu PC

1. Extraia o ZIP numa pasta curta, por exemplo `C:\Projetos\aerofox`. A pasta `.models` da versão anterior pode ser copiada para dentro dela, para não baixar os pesos de novo.
2. **Link fixo (recomendado):**
   - instale o Tailscale;
   - ative o Funnel (veja `docs/ESTABILIDADE.md`, seção 2);
   - crie o arquivo `.env` com `AEROFOX_TUNNEL=tailscale`.

   Sem isso, o padrão é o Quick Tunnel, com link aleatório.
3. Dê dois cliques em `START_AEROFOX_PUBLICO.bat` e espere a linha `PUBLIC LINK`.
4. De outro aparelho (por exemplo, o celular no 4G), abra o link e faça uma pergunta.
5. Rode o teste de carga pelo link público:
   ```
   .venv\Scripts\python.exe scripts\soak_test.py --base https://SEU-LINK --judges 3
   ```
6. Opcional:
   - `scripts\install_autostart.ps1` para início automático;
   - monitor gratuito no UptimeRobot apontando para `https://SEU-LINK/api/health`.
