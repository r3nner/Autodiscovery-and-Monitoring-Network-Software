# gerar_dicionario_json.py

import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILENAME = BASE_DIR / "mac-vendors.json"
OUTPUT_FILENAME = BASE_DIR / "oui_db.py"

def gerar_dicionario_de_json():
    """
    Lê o arquivo mac-vendors.json e gera um arquivo Python (oui_db.py)
    contendo o dicionário de fabricantes para importação rápida.
    """
    oui_db = {}

    print(f"Iniciando a leitura do arquivo '{INPUT_FILENAME.name}'...")
    
    try:
        with open(INPUT_FILENAME, 'r', encoding='utf-8') as f_in:
            # Carrega todo o conteúdo do arquivo JSON para a memória
            data = json.load(f_in)
        
        print(f"Arquivo JSON carregado. Processando {len(data)} registros...")

        # Itera sobre cada objeto (fabricante) na lista do JSON
        for entry in data:
            # Pega o prefixo MAC e o nome do fabricante de cada objeto
            prefixo_json = entry.get("macPrefix")
            fabricante = entry.get("vendorName")
            
            # Garante que ambos os campos existem antes de processar
            if prefixo_json and fabricante:
                # Formata o prefixo para o nosso padrão: '00:00:00' -> '000000'
                prefixo_final = prefixo_json.replace(':', '').upper()
                # Escapa aspas simples que podem quebrar a sintaxe do Python
                fabricante_final = fabricante.replace("'", "\\'")
                
                oui_db[prefixo_final] = fabricante_final

        print(f"Processamento concluído. {len(oui_db)} fabricantes únicos adicionados ao dicionário.")

        print(f"Gerando o arquivo '{OUTPUT_FILENAME.name}'...")
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f_out:
            f_out.write("# Este arquivo foi gerado automaticamente por gerar_dicionario_json.py\n")
            f_out.write("# Contém o dicionário de fabricantes OUI para consulta rápida.\n\n")
            f_out.write("OUI_DATABASE = {\n")
            for prefixo, fab in oui_db.items():
                f_out.write(f"    '{prefixo}': '{fab}',\n")
            f_out.write("}\n")

        print(f"\nArquivo '{OUTPUT_FILENAME.name}' gerado com sucesso!")
        print("Seu programa principal agora usará esta base de dados atualizada.")

    except FileNotFoundError:
        print(f"\nERRO: Arquivo '{INPUT_FILENAME.name}' não encontrado.")
        print("Por favor, baixe o arquivo JSON e salve-o nesta pasta com o nome correto.")
    except json.JSONDecodeError:
        print(f"\nERRO: O arquivo '{INPUT_FILENAME.name}' não é um JSON válido ou está corrompido.")

if __name__ == '__main__':
    inicio = time.time()
    gerar_dicionario_de_json()
    fim = time.time()
    print(f"\nOperação concluída em {fim - inicio:.2f} segundos.")