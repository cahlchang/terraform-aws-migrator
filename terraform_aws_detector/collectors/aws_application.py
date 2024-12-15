# terraform_aws_detector/collectors/aws_application.py

from typing import Dict, List, Any
from .base import ResourceCollector, register_collector


@register_collector
class StepFunctionCollector(ResourceCollector):
    def get_service_name(self) -> str:
        return "stepfunctions"

    def collect(self) -> List[Dict[str, Any]]:
        resources = []
        try:
            paginator = self.client.get_paginator("list_state_machines")
            for page in paginator.paginate():
                for state_machine in page["stateMachines"]:
                    # Get detailed information about the state machine
                    try:
                        details = self.client.describe_state_machine(
                            stateMachineArn=state_machine["stateMachineArn"]
                        )
                        tags = self.client.list_tags_for_resource(
                            resourceArn=state_machine["stateMachineArn"]
                        ).get("tags", [])
                    except Exception:
                        details = {}
                        tags = []

                    resources.append(
                        {
                            "type": "aws_sfn_state_machine",
                            "id": state_machine["name"],
                            "arn": state_machine["stateMachineArn"],
                            "tags": tags,
                            "details": {
                                "creation_date": str(state_machine.get("creationDate")),
                                "type": details.get("type"),
                                "status": details.get("status"),
                                "revision_id": details.get("revisionId"),
                            },
                        }
                    )
        except Exception as e:
            print(f"Error collecting Step Functions: {str(e)}")

        return resources
