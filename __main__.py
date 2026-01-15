"""
Ponto de entrada principal da infraestrutura.

USO:
pulumi stack select <shared|sandbox|production>
pulumi up
"""

import pulumi


# Determina qual stack executar baseado no nome do stack selecionado
stack_name = pulumi.get_stack()

if stack_name == "shared":
    from shared import create_shared_infra

    create_shared_infra()

elif stack_name == "sandbox":
    from sandbox import create_sandbox_env
    
    create_sandbox_env()

elif stack_name == "bonde-org":
    from bonde_org import create_bonde_org_env
    
    create_bonde_org_env()

else:
    raise ValueError(f"Stack desconhecido: {stack_name}")
