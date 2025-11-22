import pulumi
import pulumi_awsx as awsx


class NetworkStack(pulumi.ComponentResource):
    """
    NetworkStack define a VPC única e compartilhada para toda a infraestrutura.

    OBJETIVO:
    - Prover uma rede padrão (default) que será utilizada por TODOS os ambientes
    - Centralizar a configuração de rede em um único lugar
    - Permitir que múltiplos stacks (shared, sandbox, production) compartilhem a mesma VPC

    ARQUITETURA:
    Stack SHARED:    VPC + EKS Cluster (base da infra)
    Stack SANDBOX:   Apps + Services + Load Balancer (usa VPC do shared)
    Stack PRODUCTION: Apps + Services + Load Balancer (usa VPC do shared)

    CARACTERÍSTICAS:
    - VPC única: 10.0.0.0/16
    - Subnets públicas: para Load Balancers e NAT Gateways
    - Subnets privadas: para EKS Worker Nodes e aplicações
    - NAT Gateway único: economia de custos
    - Tags padronizadas: identificação e cost tracking
    """

    def __init__(self, name: str, opts=None):
        super().__init__("custom:network:NetworkStack", name, None, opts)

        config = pulumi.Config("infra-eks")
        environment = config.require("environment")

        # VPC ÚNICA E COMPARTILHADA
        # Esta VPC será utilizada por todos os stacks (shared, sandbox, production)
        # O nome inclui o environment para permitir deploy em contas diferentes,
        # mas em uma conta real, será sempre a mesma VPC física
        self.vpc = awsx.ec2.Vpc(
            f"vpc-{environment}",
            cidr_block="10.0.0.0/16",
            number_of_availability_zones=2,
            nat_gateways=awsx.ec2.NatGatewayConfigurationArgs(strategy="Single"),
            subnet_strategy="Auto",
            subnet_specs=[
                awsx.ec2.SubnetSpecArgs(
                    type=awsx.ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    tags={
                        "Name": f"public-{environment}",
                        "kubernetes.io/role/elb": "1",  # Permite ELB criar recursos
                        "Environment": environment,
                    },
                ),
                awsx.ec2.SubnetSpecArgs(
                    type=awsx.ec2.SubnetType.PRIVATE,
                    cidr_mask=24,
                    tags={
                        "Name": f"private-{environment}",
                        "kubernetes.io/role/internal-elb": "1",  # Permite internal ELB
                        "Environment": environment,
                    },
                ),
            ],
            tags={
                "Name": f"vpc-{environment}",
                "Environment": environment,
                "Project": "eks-infra",
                "ManagedBy": "pulumi",
                "Shared": "true",  # Indica que é recurso compartilhado
                "Purpose": "eks-and-apps",  # Usada tanto pelo EKS quanto pelas aplicações
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Export dos recursos de rede
        # Estes outputs serão consumidos pelos outros stacks via StackReference
        self.vpc_id = self.vpc.vpc_id
        self.public_subnet_ids = self.vpc.public_subnet_ids
        self.private_subnet_ids = self.vpc.private_subnet_ids

        self.register_outputs(
            {
                "vpc_id": self.vpc_id,
                "public_subnet_ids": self.public_subnet_ids,
                "private_subnet_ids": self.private_subnet_ids,
            }
        )


def create_network(name: str = "network-default"):
    """
    Cria a VPC única e compartilhada para a infraestrutura.

    USO:
    - Stack SHARED: cria a VPC e exporta para outros stacks
    - Stacks SANDBOX/PRODUCTION: importam a VPC via StackReference

    Args:
        name: Nome do componente (padrão: "network-default")

    Returns:
        NetworkStack: Instância da rede compartilhada
    """
    return NetworkStack(name)
