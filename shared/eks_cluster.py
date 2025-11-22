import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s

# from .alb import install_alb_controller


class EKSClusterStack(pulumi.ComponentResource):
    """
    EKSClusterStack define o cluster EKS compartilhado para todos os ambientes.

    OBJETIVO:
    - Prover um cluster Kubernetes único que será utilizado por TODOS os ambientes
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
        vpc_id: pulumi.Input[str],
        private_subnet_ids: pulumi.Input[list],
        public_subnet_ids: pulumi.Input[list],
        opts=None,
    ):
        super().__init__("custom:eks:EKSClusterStack", name, None, opts)

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
        
        
        # self.alb_controller = install_alb_controller(self.eks_cluster, self.provider)
        # Instalar ALB Controller (versão simplificada)
        # self.alb_controller = install_alb_controller(
        #     self.eks_cluster.name,  # Apenas o nome do cluster
        #     self.provider           # Provider com kubeconfig
        # )

        self.register_outputs(
            {
                "eks_cluster": self.eks_cluster,
                "node_group": self.node_group,
                "provider": self.provider,
                "kubeconfig": pulumi.Output.secret(self.kubeconfig),
                "cluster_name": self.eks_cluster.name,
                "cluster_endpoint": self.eks_cluster.endpoint,
            }
        )


def create_eks_cluster(
    name: str,
    vpc_id: pulumi.Input[str],
    private_subnet_ids: pulumi.Input[list],
    public_subnet_ids: pulumi.Input[list],
):
    """
    Cria o cluster EKS compartilhado para todos os ambientes.
    """
    return EKSClusterStack(name, vpc_id, private_subnet_ids, public_subnet_ids)
