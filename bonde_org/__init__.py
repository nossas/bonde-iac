import pulumi
import pulumi_kubernetes as k8s

from modules.ingress import create_on_demand_service, create_caddy


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

    # Caddy Ingress com Network Load Balancer AWS + On-Demand Service
    pulumi.log.info("Criando Ingress com Caddy + NLB AWS...")
    on_demand_service = create_on_demand_service(
        "on-demand",
        namespace=namespace,
        k8s_provider=k8s_provider,
        environment=stack_name,
    )
    caddy = create_caddy(
        "caddy", namespace=namespace, k8s_provider=k8s_provider, environment=stack_name
    )
    
    pulumi.export("namespace", namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)
    pulumi.log.info(f"{stack_name} com NetworkLoadBalancer automático!")
