import pulumi
import pulumi_kubernetes as k8s


class NamespaceStack(pulumi.ComponentResource):
    """
    NamespaceStack cria namespaces para isolamento de ambientes no EKS compartilhado.

    USO:
    - Stack SANDBOX: cria namespace 'sandbox'
    - Stack PRODUCTION: cria namespace 'production'
    """

    def __init__(self, name: str, k8s_provider, opts=None):
        super().__init__(f"custom:namespace:{name}", name, None, opts)

        # Configura labels baseado no ambiente
        cost_center = "development" if name == "sandbox" else "production"

        self.namespace = k8s.core.v1.Namespace(
            f"ns-{name}",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                labels={
                    "environment": name,
                    "cost-center": cost_center,
                    "managed-by": "pulumi"
                },
                annotations={
                    "pulumi.com/source": "modules/namespaces.py",
                    "environment": name,
                },
            ),
            opts=pulumi.ResourceOptions(provider=k8s_provider, parent=self),
        )

        self.register_outputs(
            {"namespace": self.namespace, "name": self.namespace.metadata["name"]}
        )


def create_namespace(name: str, k8s_provider):
    """
    Cria um namespace no cluster EKS compartilhado.

    Args:
        name: Nome do namespace (sandbox, production, etc.)
        k8s_provider: Provider Kubernetes configurado

    Returns:
        NamespaceStack: Instância do namespace criado
    """
    return NamespaceStack(name, k8s_provider)
