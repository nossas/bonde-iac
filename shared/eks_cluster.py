import json
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s

# from .alb import install_alb_controller


class EKSClusterStack(pulumi.ComponentResource):
    """
    EKSClusterStack define o cluster EKS compartilhado para todos os ambientes.

    OBJETIVO:
    - Prover um cluster Kubernetes único que será utilizado por todos os ambientes
    - Centralizar a gestão do Kubernetes em um único cluster
    - Permitir isolamento via namespaces (sandbox, production)
    - Otimizar custos com um único cluster EKS

    ARQUITETURA:
    - Cluster EKS único na VPC compartilhada
    - Node Groups nas subnets privadas
    - IAM Roles para cluster e nodes

    NOTA:
    - O EKS infere a VPC automaticamente através das subnets fornecidas
    - O vpc_id é validado implicitamente pela consistência das subnets
    """

    def __init__(
        self,
        name: str,
        private_subnet_ids: pulumi.Input[list],
        public_subnet_ids: pulumi.Input[list],
        enable_monitoring: bool = True,
        opts=None,
    ):
        super().__init__("custom:eks:EKSClusterStack", name, None, opts)

        self.name = name

        # IAM Role para o Cluster EKS
        eks_role = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=pulumi.Output.all().apply(
                lambda _: """{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "eks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }"""
            ),
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
                "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
            ],
            tags={
                "Name": f"{name}-role",
                "Environment": "shared",
                "ManagedBy": "pulumi",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Cluster EKS
        self.eks_cluster = aws.eks.Cluster(
            "eks-cluster",
            role_arn=eks_role.arn,
            vpc_config=aws.eks.ClusterVpcConfigArgs(
                subnet_ids=pulumi.Output.all(
                    private_subnet_ids, public_subnet_ids
                ).apply(lambda args: args[0] + args[1]),
                endpoint_private_access=True,
                endpoint_public_access=True,
                public_access_cidrs=["0.0.0.0/0"],
            ),
            version="1.34",  # Usar versão LTS
            tags={
                "Name": "eks-cluster",
                "Environment": "shared",
                "ManagedBy": "pulumi",
            },
            opts=pulumi.ResourceOptions(parent=self, depends_on=[eks_role]),
        )

        # IAM Role para Node Group
        node_group_role = aws.iam.Role(
            f"{name}-nodegroup-role",
            assume_role_policy=pulumi.Output.all().apply(
                lambda _: """{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ec2.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }"""
            ),
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
                "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
                "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                # Policy to use cloudwatch
                "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
                "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
            ],
            tags={
                "Name": f"{name}-nodegroup-role",
                "Environment": "shared",
                "ManagedBy": "pulumi",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Node Group
        self.node_group = aws.eks.NodeGroup(
            "eks-nodegroup",
            cluster_name=self.eks_cluster.name,
            node_role_arn=node_group_role.arn,
            subnet_ids=private_subnet_ids,
            instance_types=["t3.medium"],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=2,
                min_size=1,
                max_size=5,
            ),
            tags={
                "Name": "eks-nodegroup",
                "Environment": "shared",
                "ManagedBy": "pulumi",
            },
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.eks_cluster, node_group_role]
            ),
        )

        # Kubeconfig
        self.kubeconfig = pulumi.Output.all(
            self.eks_cluster.endpoint,
            self.eks_cluster.certificate_authority.data,
            self.eks_cluster.name,
        ).apply(
            lambda args: f"""apiVersion: v1
clusters:
- cluster:
    server: {args[0]}
    certificate-authority-data: {args[1]}
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: aws
  name: aws
current-context: aws
kind: Config
users:
- name: aws
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
      - eks
      - get-token
      - --cluster-name
      - {args[2]}
"""
        )

        # Provider Kubernetes
        self.provider = k8s.Provider(
            "k8s-provider",
            kubeconfig=self.kubeconfig,
            opts=pulumi.ResourceOptions(parent=self),
        )

        outputs = {
            "eks_cluster": self.eks_cluster,
            "node_group": self.node_group,
            "provider": self.provider,
            "kubeconfig": pulumi.Output.secret(self.kubeconfig),
            "cluster_name": self.eks_cluster.name,
            "cluster_endpoint": self.eks_cluster.endpoint,
        }

        # Garantindo que o pulumi não irá gerenciar o namespace padrão do Kubernetes
        self.kube_system_namespace = k8s.core.v1.Namespace(
            f"{name}-kube-system",  # ⚠️ NOME DEVE SER EXATO
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="kube-system",
                labels={
                    "kubernetes.io/metadata.name": "kube-system",
                    "ManagedBy": "pulumi",
                },
            ),
            opts=pulumi.ResourceOptions(
                provider=self.provider,
                parent=self,
                import_="kube-system",  # ⚠️ CRÍTICO: Diz que já existe
                ignore_changes=[
                    "metadata.annotations",  # Ignora mudanças automáticas
                    "metadata.labels",  # do Kubernetes
                    "spec.finalizers",  # Não tenta gerenciar finalizers
                ],
            ),
        )

        # INSTALAR CLOUDWATCH OBSERVABILITY ADD-ON
        if enable_monitoring:
            # 1. CloudWatch Container Insights
            self.container_insights = aws.eks.Addon(
                f"{name}-cloudwatch-observability",
                cluster_name=self.eks_cluster.name,
                addon_name="amazon-cloudwatch-observability",
                resolve_conflicts_on_create="OVERWRITE",
                resolve_conflicts_on_update="OVERWRITE",
                # service_account_role_arn=,
                configuration_values=pulumi.Output.all().apply(
                    lambda _: json.dumps(
                        {
                            "containerLogs": {
                                "enabled": True,
                            },
                        }
                    )
                ),
                tags={
                    "Name": f"{name}-cloudwatch-observability",
                    "Environment": "kube-system",
                    "ManagedBy": "pulumi",
                },
                opts=pulumi.ResourceOptions(parent=self, depends_on=[self.eks_cluster]),
            )

            # 2. Metrics Server via Helm (RÁPIDO)
            self.metrics_server = k8s.helm.v3.Release(
                f"{name}-metrics-server",
                k8s.helm.v3.ReleaseArgs(
                    chart="metrics-server",
                    version="3.12.0",
                    namespace=self.kube_system_namespace.metadata.name,
                    repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                        repo="https://kubernetes-sigs.github.io/metrics-server/"
                    ),
                    values={
                        "args": [
                            "--kubelet-insecure-tls",
                            "--kubelet-preferred-address-types=InternalIP",
                        ],
                        "replicas": 1,
                        "resources": {
                            "limits": {"cpu": "100m", "memory": "200Mi"},
                            "requests": {"cpu": "50m", "memory": "100Mi"},
                        },
                    },
                ),
                opts=pulumi.ResourceOptions(
                    provider=self.provider, parent=self, depends_on=[self.eks_cluster]
                ),
            )

            # Atualiza o LogGroup de application
            self.log_group_resources = self._update_container_insights_log_groups()

            outputs.update(
                {
                    "container_insights_enabled": enable_monitoring,
                    "metrics_server_installed": True,
                }
            )

        self.register_outputs(outputs=outputs)

    def _update_container_insights_log_groups(self):
        """Cria os 4 Log Groups padrão do Container Insights"""

        return self.eks_cluster.name.apply(
            lambda cluster_name: {
                "application": aws.cloudwatch.LogGroup(
                    f"{self.name}-ci-application",
                    name=f"/aws/containerinsights/{cluster_name}/application",
                    retention_in_days=7,
                    tags={
                        "ManagedBy": "pulumi",
                        "Environment": "shared",
                        "Cluster": cluster_name,
                    },
                    opts=pulumi.ResourceOptions(
                        import_=f"/aws/containerinsights/{cluster_name}/application"
                    ),
                ),
                "dataplane": aws.cloudwatch.LogGroup(
                    f"{self.name}-ci-dataplane",
                    name=f"/aws/containerinsights/{cluster_name}/dataplane",
                    retention_in_days=7,
                    tags={
                        "ManagedBy": "pulumi",
                        "Environment": "shared",
                        "Cluster": cluster_name,
                    },
                    opts=pulumi.ResourceOptions(
                        import_=f"/aws/containerinsights/{cluster_name}/dataplane"
                    ),
                ),
                "host": aws.cloudwatch.LogGroup(
                    f"{self.name}-ci-host",
                    name=f"/aws/containerinsights/{cluster_name}/host",
                    retention_in_days=7,
                    tags={
                        "ManagedBy": "pulumi",
                        "Environment": "shared",
                        "Cluster": cluster_name,
                    },
                    opts=pulumi.ResourceOptions(
                        import_=f"/aws/containerinsights/{cluster_name}/host"
                    ),
                ),
                "performance": aws.cloudwatch.LogGroup(
                    f"{self.name}-ci-performance",
                    name=f"/aws/containerinsights/{cluster_name}/performance",
                    retention_in_days=7,
                    tags={
                        "ManagedBy": "pulumi",
                        "Environment": "shared",
                        "Cluster": cluster_name,
                    },
                    opts=pulumi.ResourceOptions(
                        import_=f"/aws/containerinsights/{cluster_name}/performance"
                    ),
                ),
            }
        )


def create_eks_cluster(
    name: str,
    private_subnet_ids: pulumi.Input[list],
    public_subnet_ids: pulumi.Input[list],
    enable_monitoring: bool = True,
):
    """
    Cria o cluster EKS compartilhado para todos os ambientes.
    """
    return EKSClusterStack(
        name, private_subnet_ids, public_subnet_ids, enable_monitoring=enable_monitoring
    )
