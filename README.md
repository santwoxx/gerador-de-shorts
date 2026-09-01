# ⚡ AutoShorts AI - Gerador de Shorts Inteligente (YouTube -> Shorts)

Sistema completo, 100% gratuito (custo zero / free tier), que recebe links de vídeos do YouTube, analisa a transcrição com IA para identificar os momentos mais virais, fatia o vídeo em partes contínuas (ex: 10 shorts de 1 minuto), edita no formato vertical 9:16, queima legendas dinâmicas animadas e insere marca d'água/overlay personalizada do seu canal com preview ao vivo.

---

## 📖 Tutorial para Usuários
Consulte o guia completo e ilustrado em [**`TUTORIAL.md`**](file:///c:/Users/Windows/Downloads/gerador%20de%20shorts/TUTORIAL.md) para saber como instalar o Python e rodar com 2 cliques!

---

## ✨ Funcionalidades Principais

- 💰 **100% Gratuito / Custo Zero**: Roda direto no seu PC! Usa transcrições gratuitas do YouTube, yt-dlp, FFmpeg integrado e motor de IA com opções *Free Tier* (Google Gemini 2.0 Flash / Groq) ou **Motor Local Heurístico** sem necessidade de chaves de API.
- ✂️ **Modos de Corte Flexíveis**:
  - 🧠 **Highlights Virais (IA)**: Identifica ganchos iniciais, momentos de alta retenção e clímax da narrativa com nota de viralidade (0-100).
  - ✂️ **Fatiamento Sequencial Completo**: Envie um link de vídeo de 10 minutos e escolha, por exemplo, **10 shorts de 1 minuto** cobrindo do início ao fim!
  - ⚡ **Geração em Lote ("Gerar Todos")**: Gere todos os shorts selecionados com 1 clique acompanhando o progresso individual.
- 🎨 **Marca d'Água, Imagens PNG e Overlays 9:16 com Live Preview**:
  - **Editor Visual Interativo 9:16**: Veja em tempo real como o texto, a imagem sem fundo ou a moldura em tela cheia (1080x1920) ficarão no Short.
  - **Overlays Tela Cheia**: Suporte a molduras completas em 1080x1920 (como a moldura pré-definida `Gato Galudo 9:16`).
  - **Gerenciador de Predefinições (Presets)**: Salve suas marcas d'água customizadas para aplicar em qualquer vídeo com 1 clique.
- 📱 **Formatação Vertical 9:16 (1080x1920)**:
  - **🎬 Modo React / Split-Screen (Câmera + Conteúdo)**: Otimização inteligente para streamers e react! Separa a câmera e o conteúdo original empilhando em 1080x1920.
  - **📱 Fundo Desfocado (Blurred Fill)**: Vídeo original centralizado com fundo espelhado e desfocado.
  - **✂️ Recorte Central (Center Crop)**: Enquadramento direto 9:16.
  - **⬛ Barras Pretas (Letterbox)**: Mantém o formato original intacto.
- 💬 **Legendas Dinâmicas Estilizadas (ASS / Shorts Style)**:
  - Mini-chunks de 3 a 5 palavras por tela com efeito de destaque.
  - Presets: *Amarelo Viral* (estilo MrBeast/Hormozi), *Neon Cyber* (podcast moderno), *Minimalista Branco*, *Vermelho Impacto*.
- 🌐 **Interface Web Moderna**:
  - Painel escuro com Glassmorphism, animações suaves e player 9:16 para assistir antes de baixar.
  - Download direto do arquivo `.mp4` em 1 clique e histórico na Biblioteca.

---

## 🚀 Como Executar

### No Windows (1 Clique):
Dê um duplo clique no arquivo:
```cmd
run.bat
```

---

## 📁 Estrutura do Projeto

```
gerador de shorts/
├── backend/
│   ├── app.py                   # API FastAPI (rotas de análise, progresso, presets e batch)
│   ├── downloader.py            # Módulo yt-dlp para download de vídeo
│   ├── transcriber.py           # Extração gratuita de transcrição do YouTube
│   ├── ai_clipper.py            # Motor de IA e Fatiamento Sequencial
│   ├── subtitle_generator.py    # Geração de legendas dinâmicas ASS 9:16
│   └── video_processor.py       # Pipeline FFmpeg (Blur, Recorte, Overlays 9:16)
├── frontend/
│   ├── index.html               # Interface Web com Editor Visual 9:16
│   ├── style.css                # Design System Glassmorphism
│   └── app.js                   # Lógica reativa, player, live preview e chamadas de API
├── storage/
│   ├── downloads/               # Cache temporário de vídeos
│   ├── subtitles/               # Legendas geradas
│   ├── watermarks/              # Logos e Overlays salvos
│   └── outputs/                 # Shorts finalizados prontos para postar
├── requirements.txt
├── start.py
├── run.bat
├── TUTORIAL.md                  # Manual do usuário passo a passo
└── README.md
```
