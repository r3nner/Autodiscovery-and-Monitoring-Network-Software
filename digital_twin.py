

"""
Digital Twin para Mininet
Lê o banco de dados do software de autodescoberta e recria a topologia.
"""

import os
import sys

# --- CORREÇÃO DO MININET ---
# Adiciona o caminho exato onde o Mininet foi encontrado na sua VM
sys.path.append('/usr/local/lib/python3.8/dist-packages')
# ---------------------------

from mininet.net import Mininet
from mininet.node import Controller, OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink

# Adiciona o diretório atual ao path para achar o database.py
sys.path.append(os.getcwd())
import database

def create_digital_twin():
    # 1. Ler dados do Banco de Dados Real
    print("--- Consultando Banco de Dados de Autodescoberta ---")
    
    # Pega o ID do último scan realizado
    last_scan_id = database._get_latest_scan_id()
    
    if not last_scan_id:
        print("Erro: Nenhum scan encontrado no banco de dados.")
        print("Rode o 'main.py' primeiro para popular o banco.")
        return

    # Pega os dispositivos desse scan
    devices = database.get_devices_for_scan_with_first_seen(last_scan_id)
    
    # (Opcional) Pega os links se existirem, senão assume topologia estrela
    # links = database.get_links(last_scan_id) 
    
    print(f"Scan ID: {last_scan_id} | Dispositivos encontrados: {len(devices)}")

    # 2. Inicializar Mininet
    setLogLevel('info')
    
    # Limpa topologias anteriores residual
    os.system('sudo mn -c > /dev/null 2>&1')

    net = Mininet(controller=Controller, switch=OVSKernelSwitch, link=TCLink)

    info('*** Adicionando Controlador\n')
    net.addController('c0')

    info('*** Adicionando Switch Central (Core da Rede)\n')
    s1 = net.addSwitch('s1')

    # 3. Criar Hosts baseados na Realidade
    info('*** Criando Gêmeos Digitais...\n')
    
    virtual_hosts = []
    
    for dev in devices:
        ip_real = dev['ip']
        mac_real = dev['mac']
        role = dev['role']
        
        # Ignora se for o próprio gateway (pois ele será representado pelo switch ou controller na simulação simples)
        # Ou você pode criar um host especial para ele.
        
        # Cria nome seguro para o Mininet (h_192_168_0_1)
        safe_name = 'h_' + ip_real.replace('.', '_')[-3:] # Pega só o final para ficar curto ex: h_105
        
        print(f" -> Adicionando {role}: {safe_name} ({ip_real})")
        
        # Adiciona host com IP e MAC reais
        # defaultRoute é importante para eles terem conectividade simulada
        h = net.addHost(safe_name, ip=ip_real, mac=mac_real)
        
        # Configura latência simulada se tivermos o dado no banco
        latency = '1ms'
        loss = 0
        
        if dev.get('avg_latency'):
             # Mininet aceita string "10ms"
             latency = f"{dev['avg_latency']}ms"
        
        if dev.get('packet_loss'):
            loss = int(dev['packet_loss'])

        # Cria o link virtual com as características da rede real (QoS)
        # bw=10 (10Mbps simulados), delay=latencia real, loss=perda real
        net.addLink(h, s1, bw=10, delay=latency, loss=loss)
        virtual_hosts.append(h)

    # 4. Iniciar a Rede
    info('\n*** Iniciando a emulação...\n')
    net.start()
    
    info('*** Ping All (Teste de conectividade virtual)\n')
    net.pingAll()

    info('*** Executando CLI do Mininet (Digite "exit" para sair)\n')
    CLI(net)

    info('*** Parando a rede...\n')
    net.stop()

if __name__ == '__main__':
    # Verifica se está rodando como root (necessário para Mininet)
    if os.geteuid() != 0:
        print("Este script precisa ser rodado como root (sudo).")
        sys.exit(1)
        
    create_digital_twin()