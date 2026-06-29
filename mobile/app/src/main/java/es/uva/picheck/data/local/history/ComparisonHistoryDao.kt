package es.uva.picheck.data.local.history

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface ComparisonHistoryDao {
    @Query("SELECT * FROM comparison_history ORDER BY createdAtMillis DESC")
    fun observeAll(): Flow<List<ComparisonHistoryEntity>>

    @Query("SELECT * FROM comparison_history WHERE id = :id LIMIT 1")
    suspend fun getById(id: String): ComparisonHistoryEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: ComparisonHistoryEntity)

    @Query("DELETE FROM comparison_history WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM comparison_history")
    suspend fun clear()
}
