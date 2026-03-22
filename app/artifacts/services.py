from __future__ import annotations

import json
from io import BytesIO
from urllib.parse import urlparse
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.artifacts.models import ArtifactBlobContent, ArtifactBlobRecord
from app.core.config import get_settings
from app.store import ModelStore, build_model_store

DEFAULT_BUCKET = "opc-artifacts"


class ArtifactStoreService:
    def __init__(
        self,
        record_store: ModelStore[ArtifactBlobRecord],
        bucket: str = DEFAULT_BUCKET,
    ) -> None:
        self._records = record_store
        self._bucket = bucket
        self._client: Minio | None = None

    def store_json(
        self,
        *,
        source_type: str,
        source_ref: str,
        payload: dict,
        filename: str,
        summary: str,
        work_ticket_ref: str | None = None,
        thread_ref: str | None = None,
        runtrace_ref: str | None = None,
    ) -> ArtifactBlobRecord:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self._put_object(
            source_type=source_type,
            source_ref=source_ref,
            filename=filename,
            content_type="application/json",
            data=body,
            summary=summary,
            work_ticket_ref=work_ticket_ref,
            thread_ref=thread_ref,
            runtrace_ref=runtrace_ref,
        )

    def store_text(
        self,
        *,
        source_type: str,
        source_ref: str,
        text: str,
        filename: str,
        summary: str,
        work_ticket_ref: str | None = None,
        thread_ref: str | None = None,
        runtrace_ref: str | None = None,
    ) -> ArtifactBlobRecord:
        body = text.encode("utf-8")
        return self._put_object(
            source_type=source_type,
            source_ref=source_ref,
            filename=filename,
            content_type="text/plain; charset=utf-8",
            data=body,
            summary=summary,
            work_ticket_ref=work_ticket_ref,
            thread_ref=thread_ref,
            runtrace_ref=runtrace_ref,
        )

    def get_record(self, object_id: str) -> ArtifactBlobRecord | None:
        return self._records.get(object_id)

    def get_required_record(self, object_id: str) -> ArtifactBlobRecord:
        record = self.get_record(object_id)
        if record is None:
            raise KeyError(object_id)
        return record

    def list_records(self) -> list[ArtifactBlobRecord]:
        return self._records.list()

    def list_records_for_ticket(self, ticket_id: str) -> list[ArtifactBlobRecord]:
        return [record for record in self._records.list() if record.work_ticket_ref == ticket_id]

    def read_content(self, object_id: str) -> ArtifactBlobContent:
        record = self.get_required_record(object_id)
        client = self._client_for()
        try:
            response = client.get_object(record.bucket, record.object_key)
            raw = response.read()
        except S3Error as exc:
            raise ValueError(f"Failed to read artifact object: {record.object_key}") from exc
        finally:
            try:
                response.close()
                response.release_conn()
            except Exception:
                pass
        content = raw.decode("utf-8")
        return ArtifactBlobContent(record=record, content=content)

    def _put_object(
        self,
        *,
        source_type: str,
        source_ref: str,
        filename: str,
        content_type: str,
        data: bytes,
        summary: str,
        work_ticket_ref: str | None,
        thread_ref: str | None,
        runtrace_ref: str | None,
    ) -> ArtifactBlobRecord:
        object_id = f"ab-{uuid4().hex[:10]}"
        object_key = f"{source_type}/{source_ref}/{object_id}-{filename}"
        client = self._client_for()
        try:
            client.put_object(
                self._bucket,
                object_key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except S3Error as exc:
            raise ValueError(f"Failed to store artifact object: {object_key}") from exc

        record = ArtifactBlobRecord(
            object_id=object_id,
            bucket=self._bucket,
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            source_type=source_type,
            source_ref=source_ref,
            summary=summary,
            work_ticket_ref=work_ticket_ref,
            thread_ref=thread_ref,
            runtrace_ref=runtrace_ref,
            size_bytes=len(data),
        )
        return self._records.save(record)

    def _client_for(self) -> Minio:
        if self._client is not None:
            return self._client

        settings = get_settings()
        parsed = urlparse(settings.object_store_endpoint)
        endpoint = parsed.netloc or parsed.path
        secure = parsed.scheme == "https"
        client = Minio(
            endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key,
            secure=secure,
        )
        if not client.bucket_exists(self._bucket):
            client.make_bucket(self._bucket)
        self._client = client
        return client


_artifact_store_service = ArtifactStoreService(
    record_store=build_model_store(ArtifactBlobRecord, "object_id", "artifact_blob_records")
)


def get_artifact_store_service() -> ArtifactStoreService:
    return _artifact_store_service
