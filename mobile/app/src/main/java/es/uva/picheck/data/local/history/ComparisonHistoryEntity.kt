package es.uva.picheck.data.local.history

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "comparison_history")
data class ComparisonHistoryEntity(
    @PrimaryKey val id: String,
    val createdAtMillis: Long,
    val leftAppId: String,
    val leftName: String,
    val leftVersion: String?,
    val leftIntegrationModel: String?,
    val leftIcon: String?,
    val rightAppId: String,
    val rightName: String,
    val rightVersion: String?,
    val rightIntegrationModel: String?,
    val rightIcon: String?,
    val mastgIndexId: String?,
    val mastgIndexName: String?,
    val rawJson: String,
    val comparisonJson: String?,
)
