# 🍪 Vídeos com restrição de idade (+18) e "Sign in to confirm you're not a bot"

Alguns vídeos do YouTube só abrem com uma conta logada:

- vídeos com **restrição de idade (+18)**;
- vídeos **exclusivos para membros** do canal;
- qualquer vídeo quando o YouTube dispara a **verificação anti-bot**.

O app resolve isso sozinho na maior parte dos casos (ele tenta clientes de embed
e clientes alternativos automaticamente). Quando o YouTube realmente exige login,
ele abre o painel **Configurações → Acesso ao YouTube** e você escolhe um dos
três caminhos abaixo.

---

## Opção 1 — Importar do navegador (1 clique)

1. Clique em **Configurações** (topo da página).
2. Vá até **Acesso ao YouTube (Vídeos +18 / Anti-bot)**.
3. Clique em **Importar do navegador**.

O app lê a sessão já logada do Chrome, Edge, Brave, Firefox, Opera, Vivaldi ou
Chromium e salva em `storage/cookies.txt`. Nada sai do seu computador.

> **Windows:** o Chrome/Edge travam o banco de cookies enquanto estão abertos, e
> versões recentes ainda criptografam o arquivo (App-Bound Encryption). Se der
> erro, **feche o navegador por completo** (inclusive o ícone ao lado do relógio)
> e tente de novo — ou use a Opção 2, que funciona com o navegador aberto.
> O Firefox costuma funcionar mesmo aberto.

---

## Opção 2 — Enviar o arquivo cookies.txt (sempre funciona)

1. Instale a extensão gratuita **Get cookies.txt LOCALLY**:
   - [Chrome / Edge / Brave](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/pt-BR/firefox/addon/get-cookies-txt-locally/)
2. **Abra uma janela anônima** (Ctrl+Shift+N) e faça login no [YouTube.com](https://www.youtube.com) por ela.
3. Ainda na janela anônima, clique no ícone da extensão e em **Export / Download**.
4. **Feche a janela anônima sem clicar em "Sair"** da conta.
5. No app: **Configurações → Acesso ao YouTube → Enviar cookies.txt**
   (ou simplesmente **arraste o arquivo** para dentro da caixa).

> **Por que a janela anônima?** O YouTube troca os cookies de sessão o tempo
> todo enquanto você navega. Se você exportar da janela normal e continuar
> usando o YouTube nela, o arquivo exportado vira lixo em poucos minutos. Na
> janela anônima a sessão fica congelada no momento da exportação, e o arquivo
> continua valendo por semanas.

O app aceita tanto o formato **Netscape (.txt)** quanto o **JSON** do
Cookie-Editor / EditThisCookie, normaliza tudo, descarta cookies expirados e
grava em `storage/cookies.txt`.

---

## Opção 3 — Colar o conteúdo

Se preferir não mexer em arquivos: abra o `cookies.txt` no bloco de notas,
copie tudo e use **Configurações → Acesso ao YouTube → Colar conteúdo →
Salvar cookies colados**.

---

## Como saber se deu certo

O painel mostra um selo de estado:

| Selo | Significado |
| --- | --- |
| 🟢 **Ativo** | Sessão logada válida. Vídeos +18 e anti-bot liberados. |
| 🟡 **Sem login** | Há cookies do YouTube, mas nenhum de sessão. Exporte de novo **logado**. |
| 🔴 **Inválido / Não configurado** | Falta o arquivo, ele expirou ou não tem cookies do youtube.com. |

Os cookies duram algumas semanas. Se um vídeo voltar a falhar, repita a Opção 1
ou 2 para atualizá-los — o app avisa quando eles passam de 25 dias.

---

## Requisito do sistema: Node.js

Desde 2025 o YouTube exige que o programa resolva um desafio em JavaScript
antes de liberar as URLs de vídeo. Sem isso, os vídeos aparecem **sem nenhum
formato disponível** ou baixam só em 360p.

O app já traz o pacote `yt-dlp-ejs` (está no `requirements.txt`), mas ele
precisa de um motor de JavaScript instalado na máquina:

- **[Node.js 22 ou superior](https://nodejs.org)** — recomendado, é só instalar e reiniciar o app.

O painel **Acesso ao YouTube** mostra um aviso amarelo se estiver faltando, e o
terminal escreve `Motor de JavaScript ativo (node ...)` quando está tudo certo.

---

## Detalhes técnicos

- Arquivo usado: `storage/cookies.txt` (qualquer `*cookies*.txt` na pasta `storage/` também é aceito).
- **O app nunca escreve no seu arquivo de cookies.** A cada download ele entrega
  ao yt-dlp uma cópia temporária descartável, porque o yt-dlp reescreve o arquivo
  que recebe — e o YouTube às vezes manda apagar os cookies de login nessa
  reescrita, o que destruiria a sua sessão.
- Só são gravados cookies de `youtube.com`, `google.com` e domínios relacionados.
- Os cookies também são usados para baixar **as legendas** do vídeo — sem eles,
  vídeos +18 ficariam sem transcrição e os cortes sairiam sem legenda real.
- Para remover tudo: **Configurações → Acesso ao YouTube → Remover**.
