# 🔴 Como Conectar sua Conta do YouTube no AutoShorts AI

Para publicar ou programar Shorts diretamente no seu canal do YouTube, o Google exige um arquivo de autorização OAuth2 chamado `client_secrets.json`. 

Siga este passo a passo rápido de 2 minutos para obter o seu arquivo grátis:

---

## 🛠️ Passo a Passo Rápido

### **Passo 1: Acesse o Google Cloud Console**
Acesse o link direto: 👉 **[console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)**

### **Passo 2: Ative a YouTube Data API v3**
1. No menu lateral esquerdo, clique em **"Biblioteca" (Library)**.
2. Pesquise por **`YouTube Data API v3`**.
3. Clique nela e depois clique no botão azul **"Ativar" (Enable)**.

### **Passo 3: Criar as Credenciais OAuth 2.0**
1. Vá no menu **"Credenciais" (Credentials)**.
2. Clique no topo em **"+ Criar Credenciais"** -> Selecione **"ID do cliente OAuth"**.
3. Em **Tipo de aplicativo**, escolha: **`Aplicativo de Computador`** (Desktop App).
4. Defina um nome (exemplo: `AutoShorts`) e clique em **"Criar"**.

### **Passo 4: Baixar o Arquivo JSON**
1. Na janela que aparecer, clique em **"Baixar JSON"** (Download JSON).
2. O arquivo baixado terá um nome parecido com `client_secret_xxxxxxxx.json`.

### **Passo 5: Salvar no AutoShorts AI**
1. Renomeie o arquivo baixado para **`client_secrets.json`** (exatamente com esse nome).
2. Mova o arquivo para dentro da pasta do projeto no seu PC:
   📁 **`gerador de shorts/storage/yt_auth/client_secrets.json`**

---

## 🎉 Pronto!
Agora abra o AutoShorts AI, vá em qualquer Short, clique em **`🚀 Publicar / Agendar no YouTube`** e clique em **Enviar**! Uma janela do seu navegador abrirá apenas na primeira vez para você autorizar o canal.
