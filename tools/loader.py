import os
import yaml
from typing import Dict, List
from modules.apps.webservice import WebServiceConfig


def load_service_configs(environment: str) -> Dict[str, WebServiceConfig]:
    """Carrega todas as configurações de serviço de um ambiente"""
    config_dir = f"config/{environment}"
    services = {}
    
    if not os.path.exists(config_dir):
        raise Exception(f"Diretório de configuração não encontrado: {config_dir}")
    
    for filename in os.listdir(config_dir):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            service_name = filename.replace('.yaml', '').replace('.yml', '')
            config_path = os.path.join(config_dir, filename)
            
            with open(config_path, 'r') as f:
                raw_config = yaml.safe_load(f)
            
            # Valida e converte para o schema
            services[service_name] = WebServiceConfig(**raw_config)
    
    return services