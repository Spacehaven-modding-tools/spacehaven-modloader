package shl.locale;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;

/** Normalizes spaces in the two Space Haven save-slot date renderers. */
@Aspect
public class SaveDateTextNormalizer {
    @Around("call(java.lang.String java.text.DateFormat.format(java.util.Date))"
        + " && (withincode(void fi.bugbyte.spacehaven.gui.menu.GameMenu.SaveGameSlot.toggleExpand())"
        + " || withincode(void fi.bugbyte.spacehaven.gui.menu.GameMenu.CloudTab1.CloudSlot.setInfo(..)))")
    public String normalizeFormattedDate(ProceedingJoinPoint joinPoint) throws Throwable {
        String formatted = (String) joinPoint.proceed();
        return formatted == null ? null : formatted.replace('\u202f', ' ').replace('\u00a0', ' ');
    }
}
