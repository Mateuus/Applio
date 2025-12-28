# 🪟 Acessar Applio no WSL do Windows

Guia para acessar o Applio quando rodando no WSL2.

## 🔍 Problema

No WSL2, o `localhost` do Windows não acessa diretamente os containers Docker rodando no WSL. Existem algumas soluções:

## ✅ Soluções

### Solução 1: Usar IP do WSL (Recomendado)

1. **Descobrir o IP do WSL:**
   ```bash
   # No terminal WSL
   hostname -I | awk '{print $1}'
   # Ou
   ip addr show eth0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
   ```

2. **Acessar usando o IP:**
   - Interface Gradio: `http://<IP_WSL>:6969`
   - API: `http://<IP_WSL>:8000`
   
   Exemplo: `http://192.168.5.2:6969`

### Solução 2: Usar localhost (se Docker Desktop estiver configurado)

Se você está usando Docker Desktop no Windows:

1. **Verificar se o port forwarding está funcionando:**
   - Docker Desktop → Settings → Resources → WSL Integration
   - Certifique-se de que a integração WSL está habilitada

2. **Acessar normalmente:**
   - Interface Gradio: `http://localhost:6969`
   - API: `http://localhost:8000`

### Solução 3: Configurar port forwarding no Windows

Se as soluções acima não funcionarem, configure port forwarding:

```powershell
# No PowerShell do Windows (como Administrador)
netsh interface portproxy add v4tov4 listenport=6969 listenaddress=0.0.0.0 connectport=6969 connectaddress=<IP_WSL>
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<IP_WSL>
```

Substitua `<IP_WSL>` pelo IP obtido no passo 1.

## 🔧 Verificar se está funcionando

### No WSL:
```bash
# Verificar se o container está rodando
docker-compose -f docker-compose.prod.yml ps

# Verificar se a porta está exposta
docker port applio-applio-gradio-1

# Testar localmente no WSL
curl http://localhost:6969
```

### No Windows:
- Abra o navegador e acesse: `http://<IP_WSL>:6969`
- Ou se o port forwarding estiver configurado: `http://localhost:6969`

## 🐛 Troubleshooting

### Container reiniciando

Verifique os logs:
```bash
docker-compose -f docker-compose.prod.yml logs applio-gradio
```

### Porta não acessível

1. Verifique se o firewall do Windows não está bloqueando:
   ```powershell
   # No PowerShell (como Administrador)
   New-NetFirewallRule -DisplayName "WSL Docker Ports" -Direction Inbound -LocalPort 6969,8000 -Protocol TCP -Action Allow
   ```

2. Verifique se a porta está realmente exposta:
   ```bash
   docker port applio-applio-gradio-1
   ```

### Gradio escutando em 127.0.0.1

Se os logs mostram `Running on local URL: http://127.0.0.1:6969`, o Gradio não está escutando em todas as interfaces.

**Solução:** O comando já está configurado com `--host 0.0.0.0`, mas verifique se está sendo aplicado:
```bash
docker-compose -f docker-compose.prod.yml logs applio-gradio | grep "Running on"
```

Deve mostrar: `Running on local URL: http://0.0.0.0:6969` ou `Running on public URL: http://0.0.0.0:6969`

## 📝 Comandos Rápidos

```bash
# Obter IP do WSL
WSL_IP=$(hostname -I | awk '{print $1}')
echo "Acesse em: http://$WSL_IP:6969"

# Verificar portas expostas
docker-compose -f docker-compose.prod.yml ps

# Reiniciar container
docker-compose -f docker-compose.prod.yml restart applio-gradio

# Ver logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f applio-gradio
```

## 🎯 Resumo

**Para acessar do Windows quando rodando no WSL:**

1. Descubra o IP do WSL: `hostname -I | awk '{print $1}'`
2. Acesse: `http://<IP_WSL>:6969`
3. Ou configure port forwarding no Windows

**Exemplo:**
- IP do WSL: `192.168.5.2`
- Acesse: `http://192.168.5.2:6969`

