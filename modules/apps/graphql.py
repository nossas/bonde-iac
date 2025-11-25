import pulumi
import pulumi_kubernetes as k8s


class APIGraphQLService(pulumi.ComponentResource):
    """
    API-GraphQL usando Hasura Engine
    """
    
    def __init__(self, name: str, namespace: str, k8s_provider, environment: str, opts=None):
        super().__init__("custom:app:APIGraphQLService", name, None, opts)
        
        self.namespace = namespace
        
        config = pulumi.Config("apps")
        
        # Deployment do serviço api-graphql
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                namespace=namespace,
                labels={"app": "api-graphql", "component": "backend"}
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=2,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels={"app": "api-graphql"}
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        label={"app": "api-graphql"}
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name="api-graphql",
                                image="hasura/graphql-engine:v2.44.0",
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=8080, name="http"
                                    )
                                ],
                                env=[]
                            )
                        ]
                    )
                )
            )
        )