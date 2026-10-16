package dev.careerground.pace

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun PaceTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val palette = if (dark) darkColorScheme(
        primary=Color(0xFFC0D5AD), onPrimary=Color(0xFF213C2E),
        background=Color(0xFF19251D), onBackground=Color(0xFFEDF3E7),
        surface=Color(0xFF24342A), onSurface=Color(0xFFEDF3E7),
        surfaceVariant=Color(0xFF344936), onSurfaceVariant=Color(0xFFAFC1AF),
        primaryContainer=Color(0xFF344936), onPrimaryContainer=Color(0xFFEDF3E7),
        outline=Color(0xFF90A68F), outlineVariant=Color(0xFF405443),
    ) else lightColorScheme(
        primary=Color(0xFF315E49), onPrimary=Color.White,
        background=Color(0xFFFAFBF8), onBackground=Color(0xFF243B32),
        surface=Color.White, onSurface=Color(0xFF243B32),
        surfaceVariant=Color(0xFFE2EBDC), onSurfaceVariant=Color(0xFF607066),
        primaryContainer=Color(0xFFE2EBDC), onPrimaryContainer=Color(0xFF243B32),
        outline=Color(0xFF758374), outlineVariant=Color(0xFFD9E1D7),
    )
    fun text(size:Int, height:Int, weight:FontWeight=FontWeight.Normal) = TextStyle(
        fontFamily=FontFamily.SansSerif, fontSize=size.sp, lineHeight=height.sp,
        fontWeight=weight, letterSpacing=(-.3).sp)
    MaterialTheme(colorScheme=palette, typography=Typography(
        headlineLarge=text(30,43,FontWeight.SemiBold), headlineMedium=text(27,40,FontWeight.Medium),
        headlineSmall=text(24,36,FontWeight.Medium), titleLarge=text(20,30,FontWeight.Medium),
        titleMedium=text(16,25,FontWeight.Medium), bodyLarge=text(16,26), bodyMedium=text(14,23),
        bodySmall=text(12,20), labelLarge=text(14,22,FontWeight.Medium),
        labelMedium=text(12,20,FontWeight.Medium), labelSmall=text(11,18),
    ), shapes=Shapes(small=RoundedCornerShape(10.dp),medium=RoundedCornerShape(18.dp),
        large=RoundedCornerShape(24.dp)),content=content)
}
