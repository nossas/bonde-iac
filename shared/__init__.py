def create_shared_infra():
    from .network import create_network
    from .eks_cluster import create_eks_cluster

    import pulumi

    pulumi.log.info("🏗️  Criando infraestrutura compartilhada...")

    network = create_network("network-shared")
    eks_cluster = create_eks_cluster(
        "eks-shared",
        network.vpc_id,
        network.private_subnet_ids,
        network.public_subnet_ids,
    )

    # Export
    pulumi.export("vpc_id", network.vpc_id)
    pulumi.export("public_subnet_ids", network.public_subnet_ids)
    pulumi.export("private_subnet_ids", network.private_subnet_ids)
    pulumi.export("cluster_name", eks_cluster.eks_cluster.name)
    pulumi.export("kubeconfig", eks_cluster.kubeconfig)
    pulumi.export("asg_name", eks_cluster.node_group.resources.apply(lambda resources: resources[0].autoscaling_groups[0].name))