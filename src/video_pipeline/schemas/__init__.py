"""Pydantic contracts for all pipeline stage boundaries."""

from video_pipeline.schemas.character_asset import CharacterAssetEntry, CharacterAssetReport
from video_pipeline.schemas.approval import ApprovalStatus, StoryboardApprovalDocument
from video_pipeline.schemas.bgm import BGMPrepReport
from video_pipeline.schemas.gateway import (
    ChannelName,
    CharacterReferenceImage,
    GatewayPayload,
    OtherReferenceImage,
    SceneReferenceImage,
)
from video_pipeline.schemas.reference_asset import ReferenceAssetEntry, ReferenceAssetReport
from video_pipeline.schemas.plot import PlotPlan, PlotSceneOutline
from video_pipeline.schemas.intake import (
    AssetLink,
    CharacterIntakeJob,
    IntakeClarificationDocument,
    IntakeGap,
    IntakeGapResolution,
    IntakePlan,
    ReferenceIntakeJob,
    SceneIntakeJob,
    SceneShotHint,
)
from video_pipeline.schemas.keyframe import KeyframeReport, KeyframeResult
from video_pipeline.schemas.keyframe_prompt import KeyframePromptEntry, KeyframePromptsDocument
from video_pipeline.schemas.generation import (
    GenerationAttempt,
    GenerationReport,
    ShotGenerationResult,
)
from video_pipeline.schemas.job import JobStage, JobState, JobStatus
from video_pipeline.schemas.preview import StoryboardPreviewDocument, StoryboardPreviewItem
from video_pipeline.schemas.qc import QCCheckResult, QCReport
from video_pipeline.schemas.routing import RouteDecision, RoutingPlan
from video_pipeline.schemas.scene_map import SceneMapEntry, SceneMapReport
from video_pipeline.schemas.script import DialogueLine, Scene, ScriptPlan
from video_pipeline.schemas.storyboard import GenerationMode, Shot, ShotSize, ShotsDocument
from video_pipeline.schemas.tts import TTSManifest, TTSManifestEntry, TTSReport

__all__ = [
    "ApprovalStatus",
    "BGMPrepReport",
    "CharacterAssetEntry",
    "CharacterAssetReport",
    "ChannelName",
    "CharacterReferenceImage",
    "DialogueLine",
    "GatewayPayload",
    "AssetLink",
    "CharacterIntakeJob",
    "IntakeClarificationDocument",
    "IntakeGap",
    "IntakeGapResolution",
    "IntakePlan",
    "ReferenceAssetEntry",
    "ReferenceAssetReport",
    "ReferenceIntakeJob",
    "SceneIntakeJob",
    "SceneShotHint",
    "GenerationAttempt",
    "GenerationReport",
    "KeyframeReport",
    "KeyframeResult",
    "KeyframePromptEntry",
    "KeyframePromptsDocument",
    "JobStage",
    "JobState",
    "JobStatus",
    "QCCheckResult",
    "QCReport",
    "RouteDecision",
    "RoutingPlan",
    "SceneMapEntry",
    "SceneMapReport",
    "OtherReferenceImage",
    "PlotPlan",
    "PlotSceneOutline",
    "Scene",
    "SceneReferenceImage",
    "ScriptPlan",
    "GenerationMode",
    "Shot",
    "ShotSize",
    "ShotGenerationResult",
    "ShotsDocument",
    "StoryboardApprovalDocument",
    "StoryboardPreviewDocument",
    "StoryboardPreviewItem",
    "TTSManifest",
    "TTSManifestEntry",
    "TTSReport",
]
