# Makefile para Software de Autodescoberta de Rede
# Autor: Andre
# Data: Outubro 2025

# Variáveis
PYTHON := python3
VENV_DIR := venv
VENV_BIN := $(VENV_DIR)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
REQUIREMENTS := requirements.txt
MAIN_SCRIPT := main.py

# Cores para output
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
RED := \033[0;31m
NC := \033[0m # No Color

# Comandos principais
.PHONY: all help install setup run clean purge status generate-oui

# Target padrão
all: help

## help: Mostra esta mensagem de ajuda
help:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  Software de Autodescoberta de Rede - Makefile Help       ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Comandos disponíveis:$(NC)"
	@echo "  $(YELLOW)make setup$(NC)        - Instalação completa (cria venv + instala dependências)"
	@echo "  $(YELLOW)make install$(NC)      - Apenas instala/atualiza as dependências"
	@echo "  $(YELLOW)make run$(NC)          - Executa o software (requer sudo para ARP/ICMP)"
	@echo "  $(YELLOW)make generate-oui$(NC) - Gera arquivo oui_db.py a partir de mac-vendors.json"
	@echo "  $(YELLOW)make clean$(NC)        - Remove arquivos temporários e cache Python"
	@echo "  $(YELLOW)make purge$(NC)        - Remove TUDO (venv, databases, cache) - CUIDADO!"
	@echo "  $(YELLOW)make status$(NC)       - Verifica status do ambiente virtual"
	@echo "  $(YELLOW)make help$(NC)         - Mostra esta mensagem"
	@echo ""
	@echo "$(GREEN)Uso rápido:$(NC)"
	@echo "  1. Primeira vez: $(YELLOW)make setup$(NC)"
	@echo "  2. Executar:     $(YELLOW)make run$(NC)"
	@echo ""

## setup: Configuração completa do ambiente (cria venv e instala dependências)
setup: $(VENV_DIR)/bin/activate
	@echo "$(GREEN)✓ Ambiente configurado com sucesso!$(NC)"
	@echo "$(BLUE)Para executar o software, use: make run$(NC)"

## Cria o ambiente virtual e instala as dependências
$(VENV_DIR)/bin/activate: $(REQUIREMENTS)
	@echo "$(YELLOW)→ Criando ambiente virtual Python...$(NC)"
	@test -d $(VENV_DIR) || $(PYTHON) -m venv $(VENV_DIR)
	@echo "$(YELLOW)→ Atualizando pip...$(NC)"
	@$(VENV_PIP) install --upgrade pip > /dev/null 2>&1
	@echo "$(YELLOW)→ Instalando dependências do requirements.txt...$(NC)"
	@$(VENV_PIP) install -r $(REQUIREMENTS)
	@echo "$(GREEN)✓ Dependências instaladas:$(NC)"
	@$(VENV_PIP) list | grep -E "(scapy|pysnmp)"
	@touch $(VENV_DIR)/bin/activate

## install: Instala ou atualiza apenas as dependências (assume que venv existe)
install: $(VENV_DIR)/bin/activate
	@echo "$(YELLOW)→ Instalando/atualizando dependências...$(NC)"
	@$(VENV_PIP) install -r $(REQUIREMENTS)
	@echo "$(GREEN)✓ Dependências atualizadas!$(NC)"

## run: Executa o software de autodescoberta (requer sudo para scan ARP/ICMP)
run: $(VENV_DIR)/bin/activate
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  Iniciando Software de Autodescoberta de Rede             ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)⚠ AVISO: Este software requer privilégios de root/sudo$(NC)"
	@echo "$(YELLOW)  Motivo: ARP e ICMP (ping) precisam de acesso raw sockets$(NC)"
	@echo ""
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "$(RED)✗ Executando sem sudo. Reiniciando com sudo...$(NC)"; \
		sudo $(VENV_PYTHON) $(MAIN_SCRIPT); \
	else \
		$(VENV_PYTHON) $(MAIN_SCRIPT); \
	fi

## status: Verifica o status do ambiente virtual
status:
	@echo "$(BLUE)Status do Ambiente Virtual:$(NC)"
	@if [ -d $(VENV_DIR) ]; then \
		echo "  $(GREEN)✓ Virtual env existe em: $(VENV_DIR)$(NC)"; \
		echo "  $(GREEN)✓ Python: $$($(VENV_PYTHON) --version)$(NC)"; \
		echo "  $(GREEN)✓ Pip: $$($(VENV_PIP) --version | cut -d' ' -f1-2)$(NC)"; \
		echo ""; \
		echo "$(BLUE)Dependências instaladas:$(NC)"; \
		$(VENV_PIP) list | grep -E "(scapy|pysnmp)" || echo "  $(RED)✗ Nenhuma dependência encontrada$(NC)"; \
	else \
		echo "  $(RED)✗ Virtual env NÃO encontrado$(NC)"; \
		echo "  $(YELLOW)Execute 'make setup' para criar$(NC)"; \
	fi

## generate-oui: Gera o arquivo oui_db.py a partir do mac-vendors.json
generate-oui: $(VENV_DIR)/bin/activate
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  Gerando banco de dados OUI (oui_db.py)                   ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@if [ ! -f Mac-Fabricante/mac-vendors.json ]; then \
		echo "$(RED)✗ ERRO: Arquivo Mac-Fabricante/mac-vendors.json não encontrado!$(NC)"; \
		echo "$(YELLOW)  Por favor, baixe o arquivo JSON e coloque na pasta Mac-Fabricante/$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)→ Executando script de geração...$(NC)"
	@cd Mac-Fabricante && $(VENV_PYTHON) gerar_dicionario_json.py
	@if [ -f oui_db.py ]; then \
		echo ""; \
		echo "$(GREEN)✓ Arquivo oui_db.py gerado com sucesso!$(NC)"; \
		echo "$(BLUE)  Localização: Mac-Fabricante/oui_db.py$(NC)"; \
		wc -l oui_db.py | awk '{print "$(BLUE)  Total de linhas: " $$1 "$(NC)"}'; \
	else \
		echo "$(RED)✗ Falha ao gerar oui_db.py$(NC)"; \
		exit 1; \
	fi

## clean: Remove arquivos temporários e cache Python
clean:
	@echo "$(YELLOW)→ Limpando arquivos temporários...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.log" -delete 2>/dev/null || true
	@rm -f status.json 2>/dev/null || true
	@echo "$(GREEN)✓ Limpeza concluída!$(NC)"

## purge: Remove TUDO - venv, databases, cache (DESTRUTIVO!)
purge: clean
	@echo "$(RED)⚠ ATENÇÃO: Esta operação irá remover:$(NC)"
	@echo "  - Ambiente virtual (venv/)"
	@echo "  - Bancos de dados (*.db)"
	@echo "  - Todos os arquivos temporários"
	@echo ""
	@read -p "Tem certeza? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "$(YELLOW)→ Removendo ambiente virtual...$(NC)"; \
		rm -rf $(VENV_DIR); \
		echo "$(YELLOW)→ Removendo bancos de dados...$(NC)"; \
		rm -f *.db; \
		echo "$(GREEN)✓ Purge completo!$(NC)"; \
	else \
		echo "$(BLUE)Operação cancelada.$(NC)"; \
	fi
