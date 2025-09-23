# cli.py

# Importa o módulo 'cmd' para criar a interface de linha de comando.
import cmd
# Importa as configurações do projeto, como o prompt do shell.
import config
# Importa as funções de interação com o banco de dados.
import database

class ControlShell(cmd.Cmd):
    """
    Implementa o shell interativo para controlar o software de descoberta.
    """
    # Define o prompt que aparece no shell, importado do arquivo de configuração.
    intro = 'Bem-vindo ao Shell de Autodescoberta. Digite help ou ? para listar os comandos.\n'
    prompt = config.CLI_PROMPT

    def __init__(self, shared_state):
        # Inicializa a classe base cmd.Cmd.
        super().__init__()
        # Armazena a referência ao objeto de estado compartilhado entre as threads.
        self.shared_state = shared_state

    # --- Comandos do Shell ---

    def do_status(self, arg):
        """Exibe o estado atual do monitoramento e o tempo para o próximo scan."""
        # Acessa o objeto de estado compartilhado para obter o status atual.
        status = self.shared_state.get('status', 'desconhecido')
        # Acessa o objeto para obter a contagem de dispositivos.
        device_count = self.shared_state.get('device_count', 0)
        # Acessa o objeto para obter o tempo restante para o próximo scan.
        next_scan_in = self.shared_state.get('next_scan_in', 0)
        
        # Imprime as informações de status formatadas para o usuário.
        print(f"  Status: {status.capitalize()}")
        print(f"  Dispositivos no último scan: {device_count}")
        if status == 'rodando':
            print(f"  Próximo scan em: {next_scan_in:.0f} segundos")

    def help_status(self):
        # Imprime a mensagem de ajuda para o comando 'status'.
        print("Sintaxe: status")
        print("  -> Mostra o estado atual do serviço (rodando/pausado), a contagem de dispositivos")
        print("     e o tempo restante para a próxima varredura automática.")

    def do_scan(self, arg):
        """Força a execução de uma nova varredura de rede imediatamente."""
        # Define um sinalizador no estado compartilhado para forçar um scan.
        # A thread do orquestrador irá detectar essa mudança e iniciar o scan.
        self.shared_state['force_scan'] = True
        print("  -> Solicitação de scan enviada. A varredura iniciará em breve.")

    def help_scan(self):
        # Imprime a mensagem de ajuda para o comando 'scan'.
        print("Sintaxe: scan now")
        print("  -> Força uma nova varredura da rede, independentemente do tempo de espera.")
        
    def do_pause(self, arg):
        """Pausa o processo de descoberta automática em segundo plano."""
        # Altera o status no objeto compartilhado para 'pausado'.
        self.shared_state['status'] = 'pausado'
        print("  -> Descoberta automática pausada.")

    def help_pause(self):
        # Imprime a mensagem de ajuda para o comando 'pause'.
        print("Sintaxe: pause")
        print("  -> Pausa as varreduras automáticas que rodam em segundo plano.")

    def do_resume(self, arg):
        """Retoma o processo de descoberta automática em segundo plano."""
        # Altera o status no objeto compartilhado para 'rodando'.
        self.shared_state['status'] = 'rodando'
        print("  -> Descoberta automática retomada.")

    def help_resume(self):
        # Imprime a mensagem de ajuda para o comando 'resume'.
        print("Sintaxe: resume")
        print("  -> Retoma as varreduras automáticas em segundo plano.")
        
    def do_list(self, arg):
        """Lista os dispositivos descobertos no último scan: list [all|online]"""
        # Verifica se o argumento é 'online' para filtrar os resultados.
        only_online = arg.lower() == 'online'
        
        # Chama a função do banco de dados para obter os dispositivos.
        devices = database.get_last_scan_devices(only_online=only_online)

        # Verifica se a lista de dispositivos está vazia.
        if not devices:
            print("  -> Nenhum dispositivo encontrado no último scan.")
            return

        # Imprime o cabeçalho da tabela de resultados.
        print(f"{'IP':<18} {'MAC':<20} {'STATUS':<10} {'FABRICANTE'}")
        print(f"{'-'*17:<18} {'-'*19:<20} {'-'*9:<10} {'-'*20}")

        # Itera sobre a lista de dispositivos e imprime cada um formatado.
        for device in devices:
            # Garante que valores nulos sejam exibidos como 'N/A'.
            ip = device.get('ip', 'N/A')
            mac = device.get('mac', 'N/A')
            status = device.get('status', 'N/A')
            producer = device.get('producer', 'N/A')
            print(f"{ip:<18} {mac:<20} {status:<10} {producer}")

    def help_list(self):
        # Imprime a mensagem de ajuda para o comando 'list'.
        print("Sintaxe: list [all|online]")
        print("  -> Lista os dispositivos encontrados na última varredura.")
        print("  -> 'all': mostra todos os dispositivos (online e offline).")
        print("  -> 'online': mostra apenas os dispositivos que responderam ao último ping.")

    def do_exit(self, arg):
        """Encerra o shell e o programa de forma segura."""
        print("  -> Encerrando o programa...")
        # Define um sinalizador no estado compartilhado para terminar as threads.
        self.shared_state['running'] = False
        # Retorna True para que o loop do cmd.Cmd seja encerrado.
        return True

    def help_exit(self):
        # Imprime a mensagem de ajuda para o comando 'exit'.
        print("Sintaxe: exit")
        print("  -> Fecha o shell e termina a execução do programa.")
        
    def do_quit(self, arg):
        """Alias para o comando 'exit'."""
        # Chama a função do_exit para manter o comportamento consistente.
        return self.do_exit(arg)

    def help_quit(self):
        # Imprime a mensagem de ajuda para o comando 'quit'.
        print("Sintaxe: quit")
        print("  -> Alias para o comando 'exit'.")