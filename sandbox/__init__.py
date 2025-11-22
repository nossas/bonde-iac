import pulumi
import pulumi_kubernetes as k8s
from modules.caddy import create_caddy
from modules.on_demand import create_on_demand_service


def create_sandbox_env():
#     """
#     Stack SANDBOX: Ambiente completo com conexão automática ALB → Caddy
#     """
    shared_stack = pulumi.StackReference("nossas/infra-eks/shared")
    kubeconfig = shared_stack.get_output("kubeconfig")

    sandbox_provider = k8s.Provider("k8s-sandbox", kubeconfig=kubeconfig)
    
    on_demand = create_on_demand_service("on-demand", "sandbox", sandbox_provider, "sandbox")

    sandbox_namespace = k8s.core.v1.Namespace(
        "sandbox-ns",
        metadata=k8s.meta.v1.ObjectMetaArgs(name="sandbox"),
        opts=pulumi.ResourceOptions(provider=sandbox_provider),
    )

    # ✅ Caddy com LoadBalancer automático
    caddy = create_caddy("caddy", "sandbox", sandbox_provider, "sandbox")

    # ✅ Export simples
    pulumi.export("namespace", sandbox_namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)

    pulumi.log.info("🎉 SANDBOX com LoadBalancer automático!")
