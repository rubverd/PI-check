package es.uva.picheck.data.local.history

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [ComparisonHistoryEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class PiCheckDatabase : RoomDatabase() {
    abstract fun comparisonHistoryDao(): ComparisonHistoryDao

    companion object {
        @Volatile
        private var instance: PiCheckDatabase? = null

        fun getInstance(context: Context): PiCheckDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                PiCheckDatabase::class.java,
                "picheck.db",
            ).build().also { instance = it }
        }
    }
}
