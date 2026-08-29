/** Why a row is in the attention band, so the band stays meaningful. */
import { ATTENTION_LABEL, type AttentionReason } from '../lib/format'

export function AttentionTag({ reason }: { reason: AttentionReason }) {
  return <span className={`tag tag--${reason}`}>{ATTENTION_LABEL[reason]}</span>
}
