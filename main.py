# main.py

# Importa os módulos para threading e controle de tempo.
import threading
import time

# Importa os módulos específicos do nosso projeto.
import cli
import config
import database
import discovery
import utils

def run_orchestrator(shared_state, lock):
    """
    Contém a lógica principal que roda em segundo plano (thread).
    Gerencia os scans de rede, o polling adaptativo e atualiza o estado.
    """
    # Aguarda um tempo inicial antes de começar o primeiro scan.
    time.sleep(config.INITIAL_DELAY)

    # Armazena o número de dispositivos do scan anterior para a lógica adaptativa.
    last_device_count = -1
    
    # Loop principal do orquestrador. Continua enquanto o programa estiver rodando.
    while shared_state.get('running', True):
        # Adquire o lock para verificar o estado de forma segura.
        with lock:
            is_paused = shared_state.get('status') == 'pausado'
            is_forced = shared_state.get('force_scan', False)

        # Pula a iteração atual se estiver pausado e não houver um scan forçado.
        if is_paused and not is_forced:
            time.sleep(1)  # Aguarda um pouco para não consumir CPU.
            continue
        
        # --- Início do Ciclo de Descoberta ---
        print("\n(Orquestrador: Iniciando novo scan de rede...)")
        
        # Detecta a rede ativa a ser escaneada.
        # Define manualmente a rede a ser escaneada, já que a detecção automática falhou.
        # Detecta a rede ativa a ser escaneada.
        network_cidr = utils.detect_active_network()
        
        print(f"DEBUG: O script está tentando escanear a rede -> {network_cidr}")

        if not network_cidr:
            print("(Orquestrador: Erro - Não foi possível detectar a rede ativa.)")
            time.sleep(config.POLLING_INTERVAL_STABLE) # Tenta novamente após um tempo.
            continue

        # Executa o scan ARP para descobrir os dispositivos na rede.
        devices = discovery.discovery_arp(network_cidr)
        
        # Itera sobre os dispositivos encontrados para verificar o status com Ping.
        for device in devices:
            # Chama a função de ping para cada IP.
            ping_result = discovery.discovery_ping(device['ip'])
            # Atualiza o dicionário do dispositivo com o status e latência.
            device.update(ping_result)
        
        # Salva a lista completa de dispositivos no banco de dados.
        database.salvar_resultado_scan(devices)
        print("(Orquestrador: Scan concluído. Resultados salvos no banco de dados.)")
        
        # --- Lógica de Polling Adaptativo ---
        current_device_count = len(devices)
        # Escolhe o próximo intervalo de espera.
        # Se a contagem de dispositivos mudou, usa um intervalo menor.
        if current_device_count != last_device_count:
            next_interval = config.POLLING_INTERVAL_CHANGE
            print(f"(Orquestrador: Mudança detectada na rede. Próximo scan em {next_interval}s.)")
        else:
            next_interval = config.POLLING_INTERVAL_STABLE
            print(f"(Orquestrador: Rede estável. Próximo scan em {next_interval}s.)")
        
        # Atualiza a contagem de dispositivos para a próxima iteração.
        last_device_count = current_device_count

        # Adquire o lock para atualizar o estado compartilhado de forma segura.
        with lock:
            shared_state['force_scan'] = False
            shared_state['device_count'] = current_device_count

        # --- Ciclo de Espera Inteligente ---
        # Espera pelo próximo intervalo, mas verifica a cada segundo
        # se um comando (exit, scan now) foi emitido.
        for i in range(next_interval):
            # Verifica se a aplicação ainda deve rodar.
            if not shared_state.get('running'):
                break
            # Verifica se um scan foi forçado pelo usuário.
            if shared_state.get('force_scan'):
                print("(Orquestrador: Scan forçado pelo usuário. Interrompendo espera.)")
                break
            
            # Adquire o lock para atualizar o tempo restante para o próximo scan.
            with lock:
                shared_state['next_scan_in'] = next_interval - i
            
            # Aguarda por 1 segundo.
            time.sleep(1)

# Ponto de entrada principal do programa.
if __name__ == "__main__":
    # Define o estado inicial compartilhado entre a CLI e o orquestrador.
    shared_state = {
        'status': 'rodando',       # Estado atual: 'rodando' ou 'pausado'
        'running': True,           # Controla o loop principal de ambas as threads
        'force_scan': True,        # Sinalizador para forçar um scan imediato
        'device_count': 0,         # Contagem de dispositivos do último scan
        'next_scan_in': 0          # Segundos restantes para o próximo scan
    }

    # Cria um Lock para garantir o acesso seguro ao estado compartilhado.
    thread_lock = threading.Lock()

    # Inicializa o banco de dados e cria as tabelas se não existirem.
    database.inicializar_db()

    # Cria a thread para o orquestrador.
    # Define como 'daemon' para que ela encerre junto com a thread principal.
    orchestrator_thread = threading.Thread(
        target=run_orchestrator,
        args=(shared_state, thread_lock),
        daemon=True
    )
    # Inicia a execução da thread do orquestrador em segundo plano.
    orchestrator_thread.start()

    # Cria a instância do shell de controle, passando o estado compartilhado.
    shell = cli.ControlShell(shared_state)
    # Inicia o loop da CLI na thread principal, aguardando comandos do usuário.
    shell.cmdloop()

    print("Programa finalizado.")