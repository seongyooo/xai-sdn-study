"""
stage6_deploy/deployer.py — ONOS FlowRule 실제 배포

XAI 파이프라인이 APPROVE 판정을 내린 경우에만 실행된다.
배포 후 flow ID를 수집하여 반환한다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeployResult:
    """FlowRule 배포 결과"""

    success: bool
    flow_ids: list[str] = field(default_factory=list)
    error: str = ""

    def summary(self) -> str:
        if self.success:
            return f"배포 성공 ({len(self.flow_ids)}개 flow ID: {self.flow_ids})"
        return f"배포 실패: {self.error}"


class Deployer:
    """ONOS FlowRule 배포기"""

    def __init__(
        self,
        onos_url: Optional[str] = None,
        onos_user: Optional[str] = None,
        onos_password: Optional[str] = None,
    ) -> None:
        import config
        self.onos_url = onos_url or config.ONOS_URL
        self.onos_user = onos_user or config.ONOS_USER
        self.onos_password = onos_password or config.ONOS_PASSWORD

    def deploy(self, flowrule: dict) -> DeployResult:
        """
        ONOS에 FlowRule을 배포하고 flow ID를 수집한다.

        Args:
            flowrule: {"flows": [...]} 형식의 FlowRule dict

        Returns:
            DeployResult
        """
        from stage4_twin.onos_client import OnosClient, OnosError

        client = OnosClient(
            base_url=self.onos_url,
            username=self.onos_user,
            password=self.onos_password,
        )

        # 배포 전 현재 flow 목록 수집 (배포 후 새 flow 식별용)
        try:
            before_flows = client.flows()
            before_ids = {f.get("id") for f in before_flows if f.get("id")}
        except OnosError:
            before_ids = set()

        # FlowRule 배포
        try:
            client.deploy_flow_rules(flowrule)
        except OnosError as exc:
            return DeployResult(success=False, error=str(exc))
        except ValueError as exc:
            return DeployResult(success=False, error=str(exc))

        # 배포 후 flow 목록에서 새 flow ID 수집
        time.sleep(1)  # 배포 안정화 대기
        try:
            after_flows = client.flows()
        except OnosError as exc:
            # 배포는 성공했으나 flow ID 조회 실패
            return DeployResult(success=True, flow_ids=[], error=f"flow 조회 실패: {exc}")

        # 배포된 FlowRule의 priority로 필터링 (더 정확한 식별)
        target_priority = None
        flows_list = flowrule.get("flows", [])
        if flows_list:
            target_priority = flows_list[0].get("priority")

        new_flow_ids: list[str] = []
        for flow in after_flows:
            flow_id = flow.get("id")
            if not flow_id:
                continue
            # 새로 추가된 flow
            if flow_id not in before_ids:
                new_flow_ids.append(flow_id)
            # 또는 priority가 일치하는 flow (기존에 있었더라도)
            elif target_priority is not None and flow.get("priority") == target_priority:
                if flow_id not in new_flow_ids:
                    new_flow_ids.append(flow_id)

        return DeployResult(success=True, flow_ids=new_flow_ids)
