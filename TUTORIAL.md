# 📖 Tutorial Passo a Passo — AutoShorts AI

Este tutorial explica como instalar e usar o **AutoShorts AI** no Windows de forma super simples!

---

## ⚡ Passo 1: Instalar o Python no Windows

Caso ainda não tenha o Python no seu computador:

1. Baixe o Python no site oficial: [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. **IMPORTANTE durante a instalação:**
   - Marque a caixinha **`Add Python to PATH`** (ou *"Adicionar Python às variáveis de ambiente"*) na primeira tela do instalador!
3. Clique em **`Install Now`** e aguarde finalizar.

---

## 🎬 Passo 2: Como Abrir e Rodar o Programa

1. Abra a pasta do **AutoShorts AI**.
2. Dê **dois cliques** no arquivo chamado **`run.bat`**.
3. Na primeira vez, a janela preta (prompt) vai instalar automaticamente as bibliotecas necessárias.
4. Em instantes, o seu navegador de internet vai abrir automaticamente no endereço:
   `http://localhost:8000`

> 💡 **Nota:** Mantenha a janela preta aberta enquanto estiver usando o programa. Quando terminar, basta fechar a janela preta.

---

## ✂️ Passo 3: Como Usar o Gerador de Shorts

### Opção A: Fatiamento Sequencial Completo (Ex: 10 Shorts de 1 Minuto)
1. Cole o link do vídeo do YouTube na barra principal.
2. No campo **Modo de Corte**, selecione **`✂️ Fatiamento Sequencial`**.
3. Escolha a **Quantidade de Shorts** (ex: `10`) e a **Duração de cada Short** em segundos (ex: `60`).
4. Clique no botão **`Encontrar Cortes Virais`**.
5. Clique no botão verde **`Gerar Todos os 10 Shorts`** (ou gere um por um nos cards).
6. Acompanhe a barra de progresso. Quando terminar, todos os Shorts estarão prontos para download na aba **"Meus Shorts"**.

### Opção B: Seleção de Cortes Virais com IA
1. Cole o link do vídeo.
2. Mantenha o Modo de Corte em **`🧠 Highlights Virais`**.
3. A IA analisará o vídeo e encontrará automaticamente os momentos com maior potencial de retenção.
4. Clique em **`Gerar Short Vertical 9:16`** no corte desejado.

---

## 🎨 Passo 4: Marcas d'Água, Imagens PNG e Overlays 9:16

1. Clique no botão **`🎨 Editor 9:16`** no painel de configurações de Marca d'Água.
2. **Escolha o tipo:**
   - 🔤 **Texto**: Digite seu canal ou arroba (ex: `@meucanal`).
   - 🖼️ **Imagem PNG**: Faça upload da sua logo transparente.
   - 🎬 **Overlay 9:16 Tela Cheia**: Use molduras completas em 1080x1920 (como o exemplo pré-definido `Gato Galudo 9:16`).
3. Veja o **Live Preview em tempo real** no celular 9:16 que aparece na tela.
4. Ajuste tamanho, posição e transparência.
5. Clique em **`Salvar Predefinição`** para reutilizar com 1 clique sempre que quiser!

---

## 📁 Onde ficam salvos os vídeos finalizados?

Todos os Shorts gerados ficam salvos na pasta:
`storage/outputs/`

Você pode baixá-los diretamente pela interface web clicando no botão **Baixar**, ou copiar direto dessa pasta!

---

## ❓ Perguntas Frequentes

- **Preciso pagar alguma coisa?**
  Não! O sistema é 100% gratuito e roda direto no seu computador.
- **Preciso instalar o FFmpeg manualmente?**
  Não! O `run.bat` baixa tudo o que precisa automaticamente na primeira execução.
- **Dá para usar em vídeos de React / Streamers?**
  Sim! Se o sistema detectar que é um React, ele ativa automaticamente o modo **Split-Screen (Câmera do Streamer + Conteúdo)**.
