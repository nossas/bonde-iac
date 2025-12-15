import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from tools.loader import load_service_configs
from tools.envs import load_env_secrets
from modules.ingress import create_on_demand_service, create_caddy
from modules.apps.api import HasuraGateway
from modules.apps.workflows import N8NOrchestrator, N8NConfig
from modules.apps.webservice import WebService


def create_bonde_org_env():
    """
    Stack BONDE-ORG: Ambiente completo com conexão automática ALB → Caddy
    """
    stack_name = pulumi.get_stack()

    shared_stack = pulumi.StackReference("nossas/infra-eks/shared")
    kubeconfig = shared_stack.get_output("kubeconfig")

    k8s_provider = k8s.Provider(f"k8s-{stack_name}", kubeconfig=kubeconfig)

    namespace = k8s.core.v1.Namespace(
        f"{stack_name}-ns",
        metadata=k8s.meta.v1.ObjectMetaArgs(name=stack_name),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    load_env_secrets(namespace=namespace, provider=k8s_provider)

    pulumi.log.info("Criando serviço on-demand para verificação TLS...")
    on_demand_service = create_on_demand_service(
        "on-demand",
        namespace=namespace,
        k8s_provider=k8s_provider,
        environment=stack_name,
    )

    pulumi.log.info("Criando Caddy Ingress + NLB AWS...")
    caddy = create_caddy(
        name="caddy",
        namespace=stack_name,
        k8s_provider=k8s_provider,
        environment=stack_name,
        resources={
            "requests": {"memory": "500Mi", "cpu": "10m"},
            "limits": {"memory": "800Mi", "cpu": "50m"},
        },
    )

    service_loaded_configs = load_service_configs(environment=stack_name)
    created_services = {}

    for service_name, service_config in service_loaded_configs.items():
        pulumi.log.info(f"Criando serviço: {service_name}...")

        service = WebService(
            service_name,
            config=service_config,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                depends_on=[namespace, caddy, on_demand_service],
                # custom_timeouts=pulumi.CustomTimeouts(create="10m")
            ),
        )
        created_services[service_name] = service

    pulumi.log.info("Criando orquestrador de workflows com n8n...")
    n8n_orchestrator = N8NOrchestrator(
        name="n8n",
        config=N8NConfig(
            name="n8n",
            # TODO: Corrigir parâmetro namespace para utilizar a instância ao invés de um string.
            namespace=stack_name,
            webhook_url="https://n8n.bonde.org",
            image="n8nio/n8n:latest",
            replicas=1,
            resources={
                "requests": {"cpu": "20m", "memory": "500Mi"},
                "limits": {"cpu": "200m", "memory": "1Gi"},
            },
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
        ),
    )

    pulumi.log.info("Criando API-GraphQL com Hasura Engine...")
    hasura_services = {
        k: v
        for k, v in created_services.items()
        if k
        in [
            "api-accounts",
            "api-domains",
            "api-notifications",
            "api-activists",
            "api-payments",
        ]
    }
    hasura_env_vars = {
        f"{service_name.upper().replace('-', '_')}_URL": f"http://{service_name}:80"
        for service_name in hasura_services.keys()
    }

    hasura_env_vars.update({"N8N_WEBHOOK_URL": "http://n8n:80/webhook"})

    hasura_gateway = HasuraGateway(
        name="api-graphql",
        namespace=namespace,
        replicas=1,
        enable_console=True,  # Apenas em sandbox
        env_vars=hasura_env_vars,
        resources={
            "requests": {"cpu": "100m", "memory": "800Mi"},
            "limits": {"cpu": "500m", "memory": "1.5Gi"},
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            # TODO: Conferir redundancia de dependencias remote-schemas e Hasura
            depends_on=list(hasura_services.values())
            + [n8n_orchestrator],  # ⚠️ Hasura depende dos micro-serviços
        ),
    )

    pulumi.export("namespace", namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)
    pulumi.log.info(f"{stack_name} com NetworkLoadBalancer automático!")
