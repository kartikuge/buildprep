from datetime import date
from decimal import Decimal
import json

import boto3
from botocore.exceptions import ClientError

from preptrack.models.plan import WeeklyPlan
from preptrack.models.user import DayActivity, RecoveryState, TopicConfidence, UserProfile
from preptrack.storage.base import StorageBackend


def _convert_floats(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    return obj


def _convert_decimals(obj):
    """Recursively convert Decimals back to float/int."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    return obj


_TABLE_DEFS = {
    "Users": {"pk": "user_id"},
    "TopicConfidence": {"pk": "user_id", "sk": "subject"},
    "Plans": {"pk": "user_id", "sk": "week_start"},
    "ActivityLog": {"pk": "user_id", "sk": "date"},
    "LearningProfile": {"pk": "user_id", "sk": "subject"},
    "AgentSummary": {"pk": "user_id"},
    "RecoveryState": {"pk": "user_id"},
}


class DynamoLocalStorage(StorageBackend):
    def __init__(self, endpoint_url: str = "http://localhost:8000", region: str = "us-east-1"):
        self._resource = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
        self._ensure_tables()

    def _ensure_tables(self):
        existing = {t.name for t in self._resource.tables.all()}
        for table_name, keys in _TABLE_DEFS.items():
            if table_name in existing:
                continue
            key_schema = [{"AttributeName": keys["pk"], "KeyType": "HASH"}]
            attr_defs = [{"AttributeName": keys["pk"], "AttributeType": "S"}]
            if "sk" in keys:
                key_schema.append({"AttributeName": keys["sk"], "KeyType": "RANGE"})
                attr_defs.append({"AttributeName": keys["sk"], "AttributeType": "S"})
            self._resource.create_table(
                TableName=table_name,
                KeySchema=key_schema,
                AttributeDefinitions=attr_defs,
                BillingMode="PAY_PER_REQUEST",
            )

    def _table(self, name: str):
        return self._resource.Table(name)

    def _to_item(self, model) -> dict:
        data = json.loads(model.model_dump_json())
        return _convert_floats(data)

    def _get_item(self, table_name: str, key: dict) -> dict | None:
        try:
            resp = self._table(table_name).get_item(Key=key)
            item = resp.get("Item")
            return _convert_decimals(item) if item else None
        except ClientError:
            return None

    # --- UserProfile ---

    def get_user_profile(self, user_id: str) -> UserProfile | None:
        data = self._get_item("Users", {"user_id": user_id})
        return UserProfile.model_validate(data) if data else None

    def save_user_profile(self, profile: UserProfile) -> None:
        self._table("Users").put_item(Item=self._to_item(profile))

    # --- TopicConfidence ---

    def get_topic_confidences(self, user_id: str) -> list[TopicConfidence]:
        resp = self._table("TopicConfidence").query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
        )
        return [TopicConfidence.model_validate(_convert_decimals(i)) for i in resp.get("Items", [])]

    def save_topic_confidence(self, user_id: str, confidence: TopicConfidence) -> None:
        self._table("TopicConfidence").put_item(Item=self._to_item(confidence))

    # --- WeeklyPlan ---

    def get_weekly_plan(self, user_id: str, week_start: date) -> WeeklyPlan | None:
        data = self._get_item("Plans", {"user_id": user_id, "week_start": week_start.isoformat()})
        return WeeklyPlan.model_validate(data) if data else None

    def save_weekly_plan(self, plan: WeeklyPlan) -> None:
        self._table("Plans").put_item(Item=self._to_item(plan))

    # --- ActivityLog ---

    def get_activity_log(self, user_id: str, log_date: date) -> DayActivity | None:
        data = self._get_item("ActivityLog", {"user_id": user_id, "date": log_date.isoformat()})
        return DayActivity.model_validate(data) if data else None

    def save_activity_log(self, activity: DayActivity) -> None:
        self._table("ActivityLog").put_item(Item=self._to_item(activity))

    def get_pending_days(self, user_id: str, since_date: date) -> list[DayActivity]:
        resp = self._table("ActivityLog").query(
            KeyConditionExpression=(
                boto3.dynamodb.conditions.Key("user_id").eq(user_id)
                & boto3.dynamodb.conditions.Key("date").gte(since_date.isoformat())
            ),
            FilterExpression=boto3.dynamodb.conditions.Attr("finalized").eq(False),
        )
        return [DayActivity.model_validate(_convert_decimals(i)) for i in resp.get("Items", [])]

    # --- RecoveryState ---

    def get_recovery_state(self, user_id: str) -> RecoveryState | None:
        data = self._get_item("RecoveryState", {"user_id": user_id})
        return RecoveryState.model_validate(data) if data else None

    def save_recovery_state(self, state: RecoveryState) -> None:
        self._table("RecoveryState").put_item(Item=self._to_item(state))
