import pulumi
import pulumi_kubernetes as k8s

from modules.ingress import create_caddy, create_on_demand_service
from modules.apps.webservice import WebService, WebServiceConfig, ContainerConfig


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

    # Criar secrets
    config = pulumi.Config("apps")
    action_secret = k8s.core.v1.Secret(
        "action-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="action-secret",  # Nome válido: sem ":"
            namespace=sandbox_namespace.metadata["name"],
        ),
        string_data={
            "ACTION_SECRET_KEY": config.require_secret("action-secret"),
        },
        opts=pulumi.ResourceOptions(provider=sandbox_provider),
    )
    hasura_secret = k8s.core.v1.Secret(
        "hasura-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="hasura-secret",  # Nome válido: sem ":"
            namespace=sandbox_namespace.metadata["name"],
        ),
        string_data={
            "REACT_APP_API_GRAPHQL_SECRET": config.require_secret("hasura-secret"),
        },
        opts=pulumi.ResourceOptions(provider=sandbox_provider),
    )
    pagarme_secret = k8s.core.v1.Secret(
        "pagarme-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="pagarme-key",  # Nome válido: sem ":"
            namespace=sandbox_namespace.metadata["name"],
        ),
        string_data={
            "REACT_APP_PAGARME_KEY": config.require_secret("pagarme-key"),
        },
        opts=pulumi.ResourceOptions(provider=sandbox_provider),
    )

    # bonde-public
    WebService(
        name="public",
        config=WebServiceConfig(
            name="public",
            namespace="sandbox",
            replicas=2,
            container=ContainerConfig(
                image="nossas/bonde-public:latest",
                command=["pnpm", "--filter", "webpage-client", "start"],
                port=3000,
                liveness_probe_path="/api/ping",
                readiness_probe_path=None,
                env=dict(
                    PORT="3000",
                    NODE_ENV="development",
                    REACT_APP_DOMAIN_PUBLIC="sandbox.bonde.org",
                    REACT_APP_ACTIVE_API_CACHE="false",
                    # URLs de APIs externas (substituir gradualmente por serviços locais)
                    REACT_APP_DOMAIN_API_ACTIVISTS="https://api-activists.nossastech.org",
                    REACT_APP_DOMAIN_API_GRAPHQL="https://api-graphql.nossastech.org/v1/graphql",
                    REACT_APP_DOMAIN_API_REST="https://api-rest.nossastech.org",
                    REACT_APP_DOMAIN_IMAGINARY="https://imaginary.nossastech.org",
                    NEXT_PUBLIC_PHONE_API_URL="https://actions-api.nossastech.org",
                ),
                env_from_secret=dict(
                    ACTION_SECRET_KEY="action-secret",
                    REACT_APP_API_GRAPHQL_SECRET="hasura-secret",
                    REACT_APP_PAGARME_KEY="pagarme-key",
                ),
                resources={
                    "requests": {"memory": "128Mi", "cpu": "100m"},
                    "limits": {"memory": "256Mi", "cpu": "200m"},
                },
            ),
            labels=dict(component="frontend", app="public"),
        ),
        opts=pulumi.ResourceOptions(
            provider=sandbox_provider, depends_on=[caddy, on_demand_service]
        ),
    )

    # ✅ Export simples
    pulumi.export("namespace", sandbox_namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)

    pulumi.log.info("🎉 SANDBOX com LoadBalancer automático!")
