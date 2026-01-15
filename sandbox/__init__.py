import pulumi
import pulumi_kubernetes as k8s

from tools.loader import load_service_configs
from tools.envs import load_env_secrets
from modules.ingress import create_caddy, create_on_demand_service
from modules.apps.webservice import WebService
from modules.apps.api import HasuraGateway
from modules.apps.workflows import N8NOrchestrator, N8NConfig


def create_sandbox_env():
    """
    Stack SANDBOX: Ambiente completo com conexão automática ALB → Caddy
    """
    shared_stack = pulumi.StackReference("nossas/infra-eks/shared")
    kubeconfig = shared_stack.get_output("kubeconfig")

    sandbox_provider = k8s.Provider("k8s-sandbox", kubeconfig=kubeconfig)

    namespace = pulumi.get_stack()
    sandbox_namespace = k8s.core.v1.Namespace(
        "sandbox-ns",
        metadata=k8s.meta.v1.ObjectMetaArgs(name=namespace),
        opts=pulumi.ResourceOptions(provider=sandbox_provider),
    )

    # ✅ On-Demand para ser utilizado no Caddy
    on_demand_service = create_on_demand_service(
        "on-demand", namespace, sandbox_provider, "sandbox"
    )

    # ✅ Caddy com LoadBalancer automático
    caddy = create_caddy("caddy", namespace, sandbox_provider, "sandbox")

    env_secrets = load_env_secrets(
        namespace=sandbox_namespace, provider=sandbox_provider
    )

    # bonde-public
    # ✅ Carregar e criar todos os serviços
    service_loaded_configs = load_service_configs("sandbox")
    created_services = {}

    for service_name, service_config in service_loaded_configs.items():
        pulumi.log.info(f"🎯 Criando serviço: {service_name}")

        service = WebService(
            service_name,
            config=service_config,
            opts=pulumi.ResourceOptions(
                provider=sandbox_provider,
                depends_on=[sandbox_namespace, caddy, on_demand_service],
                # custom_timeouts=pulumi.CustomTimeouts(create="10m")
            ),
        )
        created_services[service_name] = service

    pulumi.log.info("🚀 Criando N8N Orchestrator")
    n8n_orchestrator = N8NOrchestrator(
        name="n8n",
        config=N8NConfig(
            name="n8n",
            namespace=namespace,
            webhook_url="https://n8n.sandbox.bonde.org",
            image="n8nio/n8n:latest",
            replicas=1,
        ),
        opts=pulumi.ResourceOptions(
            provider=sandbox_provider,
        ),
    )

    # Depois criar Hasura Gateway (depende dos micro-serviços)
    pulumi.log.info("🚀 Criando Hasura Gateway")
    hasura_services = {
        k: v
        for k, v in created_services.items()
        if k in ["api-accounts", "api-domains", "api-notifications", "api-activists", "api-payments"]
    }
    hasura_env_vars = {
        f"{service_name.upper().replace('-', '_')}_URL": f"http://{service_name}:80"
        for service_name in hasura_services.keys()
    }
    hasura_env_vars["API_UPLOADS_URL"] = "http://api-rest:80/uploads"

    hasura_env_vars.update({"N8N_WEBHOOK_URL": "http://n8n:80/webhook"})

    hasura_gateway = HasuraGateway(
        name="api-graphql",
        namespace=namespace,
        replicas=1,
        enable_console=True,  # Apenas em sandbox
        env_vars=hasura_env_vars,
        opts=pulumi.ResourceOptions(
            provider=sandbox_provider,
            # TODO: Conferir redundancia de dependencias remote-schemas e Hasura
            depends_on=list(
                hasura_services.values()
            ) + [n8n_orchestrator],  # ⚠️ Hasura depende dos micro-serviços
        ),
    )

    # ✅ Export simples
    pulumi.export("namespace", sandbox_namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)

    pulumi.log.info("🎉 SANDBOX com LoadBalancer automático!")
