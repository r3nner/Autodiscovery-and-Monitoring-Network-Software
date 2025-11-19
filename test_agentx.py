#!/usr/bin/env python3
import netsnmpagent
import ctypes
import time

print("Iniciando subagente compatível COM Debian API REAL...")

agent = netsnmpagent.netsnmpAgent(
    AgentName="DebianAgent",
    MasterSocket="/var/agentx/master",
    MIBFiles=[]
)

# Valor exposto
my_value = ctypes.c_int(777)

# Criar watcher
watcher = netsnmpagent.netsnmp_watcher_info()
watcher.type = netsnmpagent.ASN_INTEGER
watcher.data = ctypes.cast(ctypes.pointer(my_value), ctypes.c_void_p)
watcher.data_size = ctypes.sizeof(my_value)
watcher.max_size = watcher.data_size
watcher.flags = netsnmpagent.WATCHER_FIXED_SIZE

print("Criando registro...")

registration = netsnmpagent.netsnmp_handler_registration(
    b"myScalar",                  # nome
    b"1.3.6.1.4.1.53864.1",       # OID COMO STRING
    netsnmpagent.HANDLER_CAN_RONLY
)

# ANEXAR watcher ao registration
registration.handler = ctypes.cast(ctypes.pointer(watcher), ctypes.c_void_p)

print("Registrando watcher...")
agent.register(registration)

print("OK! Loop principal...")

while True:
    agent.check_and_process()
    time.sleep(0.2)
