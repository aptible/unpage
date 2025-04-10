from datetime import timedelta
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, computed_field, field_validator


class Point(BaseModel):
    """A data point in a series."""

    timestamp: AwareDatetime
    value: Decimal


class Anomaly(BaseModel):
    points: list[Point] = Field(description="The points that make up the anomaly")
    baseline: float = Field(
        description="The baseline value for the anomaly (i.e., what the anomaly was compared against)"
    )
    significance_scores: list[float] = Field(
        description="A measure of the significance of the anomaly (higher is more significant)"
    )
    description: Literal["high", "low", "jittery"] = Field(description="The nature of the anomaly")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_significance(self) -> float:
        return max(self.significance_scores)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def min_significance(self) -> float:
        return min(self.significance_scores)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_significance(self) -> float:
        return sum(self.significance_scores)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_significance(self) -> float:
        return self.total_significance / len(self.points)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def start_time(self) -> AwareDatetime:
        return self.points[0].timestamp

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end_time(self) -> AwareDatetime:
        return self.points[-1].timestamp

    @computed_field  # type: ignore[prop-decorator]
    @property
    def min_value(self) -> Decimal:
        return min(p.value for p in self.points)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_value(self) -> Decimal:
        return max(p.value for p in self.points)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time

    @field_validator("points", mode="before")
    @classmethod
    def validate_points(cls, v: list[Point]) -> list[Point]:
        """Validate that the points are sorted by timestamp."""
        return sorted(v, key=lambda x: x.timestamp)

    def __add__(self, other: "Anomaly") -> "Anomaly":
        """Merge two anomalies."""
        return Anomaly(
            points=self.points + other.points,
            significance_scores=self.significance_scores + other.significance_scores,
            baseline=(self.baseline + other.baseline) / 2,
            description=self.description if self.description == other.description else "jittery",
        )


def detect_anomalies(data: list[Point], contamination: float = 0.01) -> list[Anomaly]:
    """
    Detect anomalies in a list of (timestamp, value) tuples using pyod's Isolation Forest model.
    Also calculates a significance score for each anomaly based on its deviation from normal.

    :param data: A list of (timestamp, value) tuples.
    :param contamination: The proportion of outliers in the data set (default: 0.01).
    :return: A list of Anomaly objects that are flagged as anomalies.
    """
    import numpy as np
    from pyod.models.iforest import IForest

    if len(data) < 5:
        return []

    # Convert points to numpy array with float dtype
    points = np.array([[float(p.value)] for p in data], dtype=np.float64)

    # Handle constant values or invalid data
    if np.all(points == points[0]) or not np.all(np.isfinite(points)):
        return []

    # Calculate the range of values and the mean
    value_range = np.max(points) - np.min(points)
    mean_value = np.mean(points)

    # Values this small are effectively constant for our purposes.
    if value_range < 1e-10:
        return []

    # Use pyod's Isolation Forest to detect anomalies.
    clf = IForest(contamination=contamination, random_state=42)
    clf.fit(points)

    # Get anomaly scores (approximately -0.5 to 0.5 for IForest) and predictions (1 for outliers, 0 for inliers)
    anomaly_scores = clf.decision_function(points)
    predictions = clf.predict(points)

    if not anomaly_scores:
        return []

    # Normalize scores to 0-1 range if there are anomalies
    if np.ptp(anomaly_scores) > 0:
        anomaly_scores = (anomaly_scores - anomaly_scores.min()) / (
            anomaly_scores.max() - anomaly_scores.min()
        )

    # Return anomalous points with their significance scores and direction
    return [
        Anomaly(
            points=[point],
            significance_scores=[score],
            baseline=float(mean_value),
            description="high" if float(point.value) > mean_value else "low",
        )
        for point, score, is_anomaly in zip(data, anomaly_scores, predictions, strict=True)
        if is_anomaly
    ]


def cluster_anomalies(anomalies: list[Anomaly], threshold_seconds: int = 1800) -> list[Anomaly]:
    """
    Group anomalies into clusters based on a time threshold.

    :param anomalies: A list of Anomaly objects.
    :param threshold_seconds: Maximum gap in seconds to keep anomalies in the same cluster.
    :return: A list of Anomaly objects, where each Anomaly contains multiple points.
    """
    clusters: list[Anomaly] = []

    if not anomalies:
        return clusters

    current_cluster: Anomaly | None = None
    for anomaly in sorted(anomalies, key=lambda x: x.start_time):
        if current_cluster is None:
            # Start a new cluster with the first anomaly
            current_cluster = anomaly
        else:
            time_diff = (anomaly.start_time - current_cluster.end_time).total_seconds()

            # If the anomaly is within the threshold, merge it with the current cluster.
            if time_diff <= threshold_seconds:
                current_cluster += anomaly
            else:
                # Otherwise, finalize the current cluster and start a new one
                clusters.append(current_cluster)
                current_cluster = anomaly

    # Add the final cluster if it exists
    if current_cluster is not None:
        clusters.append(current_cluster)

    return clusters
