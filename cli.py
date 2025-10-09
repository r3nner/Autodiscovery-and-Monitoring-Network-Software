# cli.py

import cmd
import config
import database
import discovery

class ControlShell(cmd.Cmd):
    """
    Implementa o shell interativo para controlar o software de descoberta.
    """
    intro = 'Bem-vindo ao Shell de Autodescoberta. Digite help ou ? para listar os comandos.\n'
    prompt = config.CLI_PROMPT

    def __init__(self, shared_state):
        super().__init__()
        self.shared_state = shared_state

    def do_help(self, arg):
        """Lista os comandos disponíveis ou a ajuda de um comando específico."""
        if arg:
            super().do_help(arg)
        else:
            print("Comandos disponíveis (digite 'help <comando>' para mais detalhes):")
            commands = sorted([name[3:] for name in self.get_names() if name.startswith('do_')])
            for command in commands:
                print(f"  {command}")

    # --- Comandos de Controle do Serviço 
    def do_status(self, arg):
        """Exibe o estado atual do monitoramento e o tempo para o próximo scan."""
        status = self.shared_state.get('status', 'desconhecido')
        device_count = self.shared_state.get('device_count', 0)
        next_scan_in = self.shared_state.get('next_scan_in', 0)
        
        print(f"  Status: {status.capitalize()}")
        print(f"  Dispositivos no último scan: {device_count}")
        if status == 'rodando':
            print(f"  Próximo scan em: {next_scan_in:.0f} segundos")

    def help_status(self):
        print("Sintaxe: status\n  -> Mostra o estado atual do serviço (rodando/pausado) e o tempo para a próxima varredura.")

    def do_pause(self, arg):
        """Pausa o processo de descoberta automática."""
        self.shared_state['status'] = 'pausado'
        print("  -> Descoberta automática pausada.")

    def help_pause(self):
        print("Sintaxe: pause\n  -> Pausa as varreduras automáticas que rodam em segundo plano.")

    def do_resume(self, arg):
        """Retoma o processo de descoberta automática."""
        self.shared_state['status'] = 'rodando'
        print("  -> Descoberta automática retomada.")

    def help_resume(self):
        print("Sintaxe: resume\n  -> Retoma as varreduras automáticas em segundo plano.")

    def do_scan(self, arg):
        """Comando principal para gerenciar e visualizar scans."""
        parts = (arg or '').strip().split()
        if not parts:
            print("Erro: 'scan' requer um subcomando. Use 'help scan'.")
            return
        
        subcommand = parts[0].lower()
        sub_args = parts[1:]

        if subcommand == 'run':
            self._scan_run()
        elif subcommand == 'list':
            self._scan_list(sub_args)
        elif subcommand == 'view':
            self._scan_view(sub_args)
        elif subcommand == 'diff':
            self._scan_diff()
        elif subcommand == 'rollback':
            self._scan_rollback(sub_args)
        else:
            print(f"Erro: subcomando desconhecido '{subcommand}'. Use 'help scan'.")

    def help_scan(self):
        print("Gerencia e visualiza o histórico de scans de rede.\n")
        print("Uso: scan <subcomando> [argumentos]\n")
        print("Subcomandos disponíveis:")
        print("  run              - Força a execução de uma nova varredura.")
        print("  list [N]         - Lista os últimos N scans salvos (snapshots). Padrão: 10.")
        print("  view [ID]        - Mostra os dispositivos de um scan. Sem ID, mostra o último.")
        print("  diff             - Mostra as mudanças (novos/offline) do último scan.")
        print("  rollback <ID>    - (Destrutivo) Restaura o banco para o estado de um scan antigo.")

    def _scan_run(self):
        self.shared_state['force_scan'] = True
        print("  -> Solicitação de scan enviada. A varredura iniciará em breve.")

    def _scan_list(self, args):
        try:
            limit = int(args[0]) if args else 10
        except ValueError:
            print("Erro: O limite deve ser um número inteiro.")
            return
        
        history = database.get_scan_history(limit)
        if not history:
            print("  -> Nenhum histórico de scan encontrado.")
            return

        print(f"{'SCAN_ID':<8} {'TIMESTAMP':<26} {'TOTAL':<7} {'ONLINE'}")
        print(f"{'-'*7:<8} {'-'*25:<26} {'-'*6:<7} {'-'*6}")
        for r in history:
            online = r.get('online_count') or 0
            print(f"{r.get('scan_id'):<8} {str(r.get('timestamp')):<26} {r.get('total',0):<7} {online}")


    def _scan_view(self, args):
        scan_id = None
        if args:
            try:
                scan_id = int(args[0])
            except ValueError:
                print("Erro: ID do scan inválido. Deve ser um número.")
                return
        
        devices = database.get_devices_for_scan_with_first_seen(scan_id)
        if not devices:
            print("  -> Nenhum dispositivo encontrado para este scan.")
            return

        self._print_device_table(devices)

    def _print_device_table(self, devices):
        """Função auxiliar para imprimir tabelas de dispositivos de forma consistente."""
        print(f"{'IP':<18} {'MAC':<20} {'STATUS':<10} {'PAPEL':<10} {'FABRICANTE':<25} {'PRIMEIRA DESCOBERTA'}")
        print(f"{'-'*17:<18} {'-'*19:<20} {'-'*9:<10} {'-'*9:<10} {'-'*24:<25} {'-'*20}")
        for d in devices:
            print(f"{(d.get('ip') or 'N/A'):<18} {(d.get('mac') or 'N/A'):<20} {(d.get('status') or 'N/A'):<10} {(d.get('role') or 'N/A'):<10} {(d.get('producer') or 'N/A'):<25} {str(d.get('first_seen') or 'N/A')}")
    def _scan_diff(self):
        changes = database.get_changes_for_last_scan()
        new_list = changes.get('new', [])
        off_list = changes.get('offline', [])

        print("\n--- Novos Dispositivos ---")
        if not new_list:
            print("  (nenhum)")
        else:
            self._print_device_table(new_list)

        print("\n--- Dispositivos Ficaram Offline ---")
        if not off_list:
            print("  (nenhum)")
        else:
            self._print_device_table(off_list)


    def _scan_rollback(self, args):
        if not args:
            print("Erro: 'rollback' requer um ID de scan.")
            return
        try:
            scan_id = int(args[0])
            deleted = database.rollback_to_scan(scan_id)
            print(f"  -> Rollback concluído. {deleted} scan(s) mais novo(s) foram apagados.")
        except ValueError:
            print("Erro: ID do scan inválido. Deve ser um número.")

    def do_snmp(self, arg):
        """Testa a conectividade SNMP básica com um dispositivo."""
        parts = (arg or '').strip().split()
        if len(parts) != 2 or parts[0].lower() != 'test':
            self.help_snmp()
            return
        
        ip = parts[1]
        print(f"  -> Testando SNMP em {ip}...")
        info = discovery.discovery_snmp_basic(ip)
        if not info:
            print("  -> SNMP indisponível ou sem resposta.")
            return
        print("  -> Resposta SNMP básica recebida:")
        print(f"     Nome (sysName): {info.get('snmp_name')}")
        print(f"     Descrição (sysDescr): {info.get('snmp_description')}")

    def help_snmp(self):
        print("Sintaxe: snmp test <ip>\n  -> Testa as credenciais SNMP básicas em um dispositivo.")


    def do_config(self, arg):
        """Gerencia configurações em tempo de execução: config [show|set <chave> <valor>]."""
        parts = (arg or '').strip().split()
        if not parts:
            self.help_config()
            return
        
        subcommand = parts[0].lower()
        
        if subcommand == 'show':
            self._config_show()
            return
            
        if subcommand == 'set' and len(parts) >= 3:
            key = parts[1].lower()
            value = " ".join(parts[2:])
            self._config_set(key, value)
            return
            
        self.help_config()

    def help_config(self):
        print("Gerencia as configurações em tempo de execução.\n")
        print("Uso: config <subcomando> [argumentos]\n")
        print("Subcomandos e Chaves Disponíveis:")
        print("  show")
        print("  set interval stable <segundos>")
        print("  set interval change <segundos>")
        print("  set timeout <segundos>")
        print("  set network <CIDR> | auto")
        print("  set snmp version <2c|3>")
        print("  set snmp community <string>")
        print("  set snmp timeout <segundos>")
        print("  set snmp retries <numero>")
        print("  set snmp port <numero>")

    def _config_show(self):
        st = self.shared_state
        print("--- Configurações Atuais em Tempo de Execução ---")
        print(f"  Intervalo (rede estável): {st.get('interval_stable')}s")
        print(f"  Intervalo (rede mudou):   {st.get('interval_change')}s")
        print(f"  Timeout do Scan:          {st.get('scan_timeout')}s")
        print(f"  Rede Alvo:                {st.get('network_cidr') or 'auto'}")
        print("  SNMP:")
        print(f"    Versão:    {st.get('snmp_version', '2c')}")
        print(f"    Community: {st.get('snmp_community', 'public')}")
        print(f"    Timeout:   {st.get('snmp_timeout', 1)}s")
        print(f"    Retries:   {st.get('snmp_retries', 0)}")
        print(f"    Porta:     {st.get('snmp_port', 161)}")

    def _config_set(self, key, value):
        st = self.shared_state
        try:
            if key == 'interval':
                parts = value.split()
                if len(parts) != 2 or parts[0] not in ('stable', 'change'):
                    print("  -> Uso: config set interval [stable|change] <segundos>")
                    return
                which, sval = parts
                ival = int(sval)
                if ival <= 0: raise ValueError("O intervalo deve ser positivo.")
                
                st[f'interval_{which}'] = ival
                print(f"  -> Intervalo '{which}' atualizado para {ival}s.")

            elif key == 'timeout':
                ival = int(value)
                if ival <= 0: raise ValueError("O timeout deve ser positivo.")
                st['scan_timeout'] = ival
                print(f"  -> Timeout de scan atualizado para {ival}s.")

            elif key == 'network':
                val = value.strip()
                if val.lower() == 'auto':
                    st['network_cidr'] = None
                    print("  -> Rede alvo definida para 'auto'.")
                else:
                    if '/' not in val:
                        print("  -> Formato de rede inválido. Use CIDR (ex: 192.168.1.0/24) ou 'auto'.")
                        return
                    st['network_cidr'] = val
                    print(f"  -> Rede alvo atualizada para '{val}'.")
            
            elif key == 'snmp':
                parts = value.split()
                if len(parts) < 2:
                    print("  -> Uso: config set snmp [version|community|timeout|retries|port] <valor>")
                    return
                
                k = parts[0].lower()
                v = " ".join(parts[1:]).strip()

                if k == 'version':
                    if v not in ('2c', '3'):
                        print("  -> Versão SNMP inválida. Use '2c' ou '3'.")
                        return
                    st['snmp_version'] = v
                    print(f"  -> Versão SNMP atualizada para '{v}'.")
                elif k == 'community':
                    st['snmp_community'] = v
                    print(f"  -> SNMP community atualizada para '{v}'.")
                elif k in ('timeout', 'retries', 'port'):
                    ival = int(v)
                    if ival < 0: raise ValueError("Valor deve ser não-negativo.")
                    st[f'snmp_{k}'] = ival
                    print(f"  -> SNMP {k} atualizado para {ival}.")
                else:
                    print(f"  -> Parâmetro SNMP '{k}' desconhecido.")
            else:
                print(f"  -> Chave de configuração '{key}' desconhecida.")

        except (ValueError, TypeError) as e:
            print(f"  -> Valor inválido. Forneça um número inteiro quando aplicável. ({e})")


    def do_exit(self, arg):
        """Encerra o shell e o programa."""
        print("  -> Encerrando o programa...")
        self.shared_state['running'] = False
        return True

    def help_exit(self):
        print("Sintaxe: exit\n  -> Fecha o shell e termina a execução do programa.")
        
    def do_quit(self, arg):
        """Alias para o comando 'exit'."""
        return self.do_exit(arg)

    def help_quit(self):
        print("Sintaxe: quit\n  -> Alias para o comando 'exit'.")