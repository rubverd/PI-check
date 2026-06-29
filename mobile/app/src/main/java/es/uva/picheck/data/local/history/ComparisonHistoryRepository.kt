package es.uva.picheck.data.local.history

import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.data.remote.PiCheckApiClient
import kotlinx.coroutines.flow.Flow

class ComparisonHistoryRepository(
    private val dao: ComparisonHistoryDao,
) {
    fun observeHistory(): Flow<List<ComparisonHistoryEntity>> = dao.observeAll()

    suspend fun save(result: PiCheckComparisonAnalysis) {
        dao.upsert(result.toHistoryEntity())
    }

    suspend fun getResult(id: String): PiCheckComparisonAnalysis? {
        val entity = dao.getById(id) ?: return null
        return parseStoredResult(entity.rawJson)
            ?: entity.comparisonJson?.let { parseStoredResult(it) }
    }

    suspend fun delete(id: String) {
        dao.deleteById(id)
    }

    suspend fun clear() {
        dao.clear()
    }

    private fun parseStoredResult(rawJson: String): PiCheckComparisonAnalysis? = runCatching {
        PiCheckApiClient.parseComparisonAnalysis(rawJson)
    }.getOrNull()
}
