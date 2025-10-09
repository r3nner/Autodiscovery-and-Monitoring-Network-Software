# Software de Autodescoberta de Rede

Sistema completo de descoberta e monitoramento de dispositivos em rede local utilizando **ARP**, **PING** e **SNMP**.

---

## 📋 Índice

- [Características](#características)
- [Requisitos](#requisitos)
- [Instalação e Execução](#instalação-e-execução)
- [Comandos do Makefile](#comandos-do-makefile)
- [Comandos da CLI](#comandos-da-cli)
- [Configurações](#configurações)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## ✨ Características

- 🔍 **Descoberta Automática**: Scan de rede via ARP para detectar dispositivos
- 📡 **Monitoramento SNMP**: Identifica papel (roteador/host) e informações detalhadas
- 🏷️ **Identificação de Fabricante**: Correlação MAC → Fabricante (banco OUI local)
- 📊 **Histórico de Scans**: Sistema de snapshots com banco de dados SQLite
- ⚡ **Polling Adaptativo**: Ajusta frequência de scans baseado em mudanças na rede
- 🎛️ **Configuração Dinâmica**: Altera parâmetros em tempo real sem reiniciar
- 🔐 **Suporte SNMPv2c/v3**: Flexibilidade para diferentes ambientes

---

## 🔧 Requisitos

### Sistema Operacional

- **Linux** (testado em Ubuntu/Debian)
- Também funciona em macOS e Windows (com adaptações)

### Software

- **Python 3.8+**
- **sudo/root** (necessário para ARP e ICMP raw sockets)
- **make** (opcional, mas recomendado)

### Dependências Python

- `scapy==2.5.0` - Manipulação de pacotes de rede
- `pysnmp==4.4.12` - Protocolo SNMP

---

## 🚀 Instalação e Execução

### Método 1: Usando Makefile (Recomendado)

#### 1️⃣ Instalação (Primeira vez)

```bash
make setup
```

**O que acontece:**

1. ✅ Cria um ambiente virtual Python em `venv/`
2. ✅ Atualiza o `pip` para a versão mais recente
3. ✅ Instala todas as dependências do `requirements.txt`
4. ✅ Verifica e exibe as bibliotecas instaladas

**Tempo estimado:** 30-60 segundos

---

#### 2️⃣ Execução

```bash
make run
```

**O que acontece:**

1. ✅ Verifica se o ambiente virtual existe
2. ⚠️ Detecta se você está sem `sudo` e automaticamente reinicia com privilégios
3. 🚀 Inicia o software com shell interativo
4. 🔄 Começa o monitoramento automático em segundo plano

**Saída esperada:**

```text
╔════════════════════════════════════════════════════════════╗
║  Iniciando Software de Autodescoberta de Rede              ║
╚════════════════════════════════════════════════════════════╝

⚠ AVISO: Este software requer privilégios de root/sudo
  Motivo: ARP e ICMP (ping) precisam de acesso raw sockets

(Database: Banco de dados inicializado com sucesso.)
Bem-vindo ao Shell de Autodescoberta. Digite help ou ? para listar os comandos.

(discovery-shell)
```

---

### Método 2: Manual (Sem Makefile)

```bash
# 1. Criar ambiente virtual
python3 -m venv venv

# 2. Ativar ambiente virtual
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Executar com sudo
sudo venv/bin/python main.py
```

---

## 🛠️ Comandos do Makefile

| Comando       | Descrição                       | Quando usar                                   |
|---------------|---------------------------------|-----------------------------------------------|
| `make setup`  | Instalação completa do ambiente | **Primeira vez** ou após clonar o repositório |
| `make run`    | Executa o software              | **Sempre** que quiser rodar o programa        |
| `make install`| Atualiza dependências           | Após modificar `requirements.txt`             |
| `make status` | Verifica ambiente virtual       | Diagnóstico de problemas                      |
| `make clean`  | Remove cache e temporários      | Limpeza de arquivos `.pyc`, logs              |
| `make purge`  | Remove TUDO (venv, DB)          | **CUIDADO!** Apaga ambiente e dados           |
| `make help`   | Mostra ajuda do Makefile        | Listar todos os comandos                      |

---

## 💻 Comandos da CLI

Após executar `make run`, você terá acesso a um shell interativo com os seguintes comandos:

### 📊 Monitoramento e Status

#### `status`

Exibe o estado atual do sistema.

**Exemplo de saída:**

```text
(discovery-shell) status
  Status: Rodando
  Dispositivos no último scan: 5
  Próximo scan em: 342 segundos
```

---

### 🔍 Gerenciamento de Scans

#### `scan run`

Força uma varredura imediata da rede.

```bash
(discovery-shell) scan run
  -> Solicitação de scan enviada. A varredura iniciará em breve.
```

---

#### `scan list [N]`

Lista os últimos N scans realizados (padrão: 10).

**Exemplo:**

```text
(discovery-shell) scan list 5

SCAN_ID  TIMESTAMP                  TOTAL   ONLINE
-------  -------------------------  ------  ------
15       2025-10-09 14:30:25        8       6
14       2025-10-09 14:20:12        7       5
13       2025-10-09 14:10:05        7       5
```

---

#### `scan view [ID]`

Mostra todos os dispositivos de um scan específico. Sem ID, mostra o último scan.

**Exemplo:**

```text
(discovery-shell) scan view 15

IP                 MAC                  STATUS     PAPEL      FABRICANTE                PRIMEIRA DESCOBERTA
-----------------  -------------------  ---------  ---------  ------------------------  --------------------
192.168.1.1        aa:bb:cc:dd:ee:ff    online     Roteador   TP-Link                   2025-10-09 10:15:30
192.168.1.10       11:22:33:44:55:66    online     Host       Dell Inc.                 2025-10-09 10:15:30
```

---

#### `scan diff`

Compara os 2 últimos scans e mostra as mudanças (novos dispositivos e offline).

**Exemplo:**

```text
(discovery-shell) scan diff

--- Novos Dispositivos ---
IP                 MAC                  STATUS     PAPEL      FABRICANTE
-----------------  -------------------  ---------  ---------  ------------------------
192.168.1.50       aa:11:22:33:44:55    online     Host       Apple

--- Dispositivos Ficaram Offline ---
  (nenhum)
```

---

#### `scan rollback <ID>`

⚠️ **DESTRUTIVO!** Apaga todos os scans mais novos que o ID especificado.

```bash
(discovery-shell) scan rollback 12
  -> Rollback concluído. 3 scan(s) mais novo(s) foram apagados.
```

---

### 🌐 Teste SNMP

#### `snmp test <IP>`

Testa conectividade SNMP com um dispositivo específico.

**Exemplo:**

```text
(discovery-shell) snmp test 192.168.1.1
  -> Testando SNMP em 192.168.1.1...
  -> Resposta SNMP básica recebida:
     Nome (sysName): Router-Principal
     Descrição (sysDescr): Linux 4.9.0 router
```

---

### ⚙️ Configurações

#### `config show`

Exibe todas as configurações atuais.

**Exemplo:**

```text
(discovery-shell) config show

--- Configurações Atuais em Tempo de Execução ---
  Intervalo (rede estável): 600s
  Intervalo (rede mudou):   60s
  Timeout do Scan:          1s
  Rede Alvo:                auto
  SNMP:
    Versão:    2c
    Community: public
    Timeout:   1s
    Retries:   0
    Porta:     161
```

---

#### `config set <chave> <valor>`

Altera configurações em tempo real.

**Exemplos:**

```bash
# Alterar intervalos de polling
config set interval stable 300    # 5 minutos quando estável
config set interval change 30     # 30 segundos após mudança

# Alterar timeout de scan
config set timeout 2              # 2 segundos

# Definir rede específica ou auto-detect
config set network 192.168.1.0/24
config set network auto

# Configurações SNMP
config set snmp version 2c
config set snmp community private
config set snmp timeout 2
config set snmp retries 2
config set snmp port 161
```

---

### 🚪 Saída

#### `exit` ou `quit`

Encerra o programa.

```bash
(discovery-shell) exit
  -> Encerrando o programa...
Programa finalizado.
```

---

## ⚙️ Referência de Configurações

### Arquivo: config.py

| Configuração              | Padrão   | Descrição                          |
|---------------------------|----------|------------------------------------|
| `SCAN_TIMEOUT`            | 1s       | Timeout para ARP scan              |
| `POLLING_INTERVAL_STABLE` | 600s     | Intervalo quando rede está estável |
| `POLLING_INTERVAL_CHANGE` | 60s      | Intervalo após detectar mudança    |
| `SNMP_VERSION`            | "2c"     | Versão SNMP (2c ou 3)              |
| `SNMP_COMMUNITY`          | "public" | Community string SNMP              |
| `SNMP_TIMEOUT`            | 1s       | Timeout para consultas SNMP        |
| `SNMP_RETRIES`            | 0        | Tentativas em caso de falha        |
| `SNMP_PORT`               | 161      | Porta SNMP padrão                  |

Todas podem ser alteradas em tempo real via comando `config set`.

---

## 📁 Estrutura do Projeto

```text
.
├── main.py                 # Orquestrador principal + thread de monitoramento
├── cli.py                  # Shell interativo (comandos)
├── config.py               # Configurações centralizadas
├── discovery.py            # Funções de descoberta (ARP, PING, SNMP)
├── database.py             # Gerenciamento SQLite (scans, dispositivos)
├── utils.py                # Utilitários (detecção de rede ativa)
├── oui_db.py               # Banco de fabricantes (MAC → Vendor)
├── requirements.txt        # Dependências Python
├── Makefile                # Automação de instalação/execução
├── README.md               # Este arquivo
├── network_data.db         # Banco SQLite (gerado automaticamente)
└── Mac-Fabricante/
    └── mac-vendors.json    # Base de dados OUI (fabricantes)
```

---

## 🎯 Resumo Rápido

```bash
# Instalação (primeira vez)
make setup

# Executar
make run

# Dentro do shell
status              # Ver estado
scan run            # Forçar scan
scan list           # Ver histórico
scan view           # Ver dispositivos
scan diff           # Ver mudanças
config show         # Ver configurações
exit                # Sair
```

---

## 📝 Notas Importantes

1. **Sudo é obrigatório**: ARP e ICMP requerem raw sockets (privilégios de root)
2. **Firewall**: Certifique-se que SNMP (UDP 161) não está bloqueado
3. **Community SNMP**: Padrão é "public" - ajuste conforme sua rede
4. **Banco de dados**: Criado automaticamente em `network_data.db`

---

## 🐛 Troubleshooting

### Erro: "Permission denied" ao executar

**Solução:** Use `make run` (já inclui sudo) ou `sudo venv/bin/python main.py`

### Erro: "No module named 'scapy'"

**Solução:** Execute `make setup` para instalar dependências

### SNMP não funciona

**Solução:**

1. Verifique se o dispositivo tem SNMP habilitado
2. Teste: `snmp test <IP_DO_DISPOSITIVO>`
3. Ajuste community: `config set snmp community <sua_community>`

---

## 👨‍💻 Autor

**Andre Renner**  
Gerenciamento de Redes 'A' - 4° Semestre  
Data: Outubro 2025

---

## 📜 Licença

Este projeto é de uso acadêmico.
