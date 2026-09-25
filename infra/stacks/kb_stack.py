"""Bedrock Knowledge Base over the maintenance manuals, stored in Amazon S3 Vectors.

S3 Vectors has no always-on compute (unlike OpenSearch Serverless, which bills for OCUs
around the clock), so the idle cost of the RAG layer is storage only.
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_s3vectors as s3vectors
from constructs import Construct

from settings import ROOT, Settings
from stacks.data_stack import private_bucket

MANUALS_PREFIX = "manuals/"


class KnowledgeBaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, settings: Settings, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cfg = settings.bedrock
        embedding_arn = f"arn:aws:bedrock:{self.region}::foundation-model/{cfg['embedding_model_id']}"

        docs_bucket = private_bucket(self, "ManualsBucket")
        s3deploy.BucketDeployment(
            self,
            "Manuals",
            sources=[s3deploy.Source.asset(str(ROOT / "kb"))],
            destination_bucket=docs_bucket,
            destination_key_prefix=MANUALS_PREFIX,
        )

        vector_bucket = s3vectors.CfnVectorBucket(self, "VectorBucket")
        index = s3vectors.CfnIndex(
            self,
            "VectorIndex",
            vector_bucket_arn=vector_bucket.attr_vector_bucket_arn,
            data_type="float32",
            dimension=int(cfg["embedding_dimension"]),
            distance_metric="cosine",
            # Bedrock stores chunk text + source metadata on each vector; keep them out of the
            # filterable-metadata size limit.
            metadata_configuration=s3vectors.CfnIndex.MetadataConfigurationProperty(
                non_filterable_metadata_keys=["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
            ),
        )

        kb_role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com").with_conditions({
                "StringEquals": {"aws:SourceAccount": self.account},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"},
            }),
        )
        kb_role.add_to_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[embedding_arn]))
        docs_bucket.grant_read(kb_role, f"{MANUALS_PREFIX}*")
        kb_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3vectors:PutVectors", "s3vectors:GetVectors", "s3vectors:DeleteVectors",
                "s3vectors:QueryVectors", "s3vectors:GetIndex", "s3vectors:ListVectors",
            ],
            resources=[index.attr_index_arn],
        ))

        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=f"{settings.project}-manuals",
            description="MaintainOps maintenance manuals (S3 Vectors)",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_arn,
                    embedding_model_configuration=bedrock.CfnKnowledgeBase.EmbeddingModelConfigurationProperty(
                        bedrock_embedding_model_configuration=bedrock.CfnKnowledgeBase.BedrockEmbeddingModelConfigurationProperty(
                            dimensions=int(cfg["embedding_dimension"]),
                            embedding_data_type="FLOAT32",
                        )
                    ),
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="S3_VECTORS",
                s3_vectors_configuration=bedrock.CfnKnowledgeBase.S3VectorsConfigurationProperty(
                    index_arn=index.attr_index_arn,
                ),
            ),
        )
        # the role's policy must exist before Bedrock validates access to the index
        self.knowledge_base.node.add_dependency(kb_role)

        self.data_source = bedrock.CfnDataSource(
            self,
            "ManualsDataSource",
            name="maintenance-manuals",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_deletion_policy="DELETE",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=docs_bucket.bucket_arn,
                    inclusion_prefixes=[MANUALS_PREFIX],
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300, overlap_percentage=15
                    ),
                )
            ),
        )

        self.knowledge_base_id = self.knowledge_base.attr_knowledge_base_id
        self.knowledge_base_arn = self.knowledge_base.attr_knowledge_base_arn
        CfnOutput(self, "KnowledgeBaseId", value=self.knowledge_base_id)
        CfnOutput(self, "DataSourceId", value=self.data_source.attr_data_source_id)
