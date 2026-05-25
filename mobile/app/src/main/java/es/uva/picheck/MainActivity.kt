package es.uva.picheck

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import es.uva.picheck.ui.screens.AppSearchScreen
import es.uva.picheck.ui.theme.PiCheckTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            PiCheckTheme {
                AppSearchScreen()
            }
        }
    }
}