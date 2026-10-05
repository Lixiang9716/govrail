# Agent Note: verify-pairing 绿输出声明范围;作者时刻教互链形态(#426/#427/D70)

Status: implemented

## Problem

双语约定被两个命令各管一半(#426):`verify-pairing` 本地绿(配对存在+摘要一致),CI 的 doc-crosslinks 门红(互链缺失)——作者跑了文档化的本地预检,失败却从 CI 学到,本地绿被读作"合规"。互链的期望形态(行 2 双向 `English | [简体中文](stem.zh.md)`、H1 之下)只能翻合规文件反推(#427):失败消息与本地输出都不教。

## Decision

验证器在说"绿"的地方同时说自己不是什么:全量绿与 --staged 绿输出追加一行范围声明——"scope: existence + digests; cross-language links NOT checked here(采用方的 crosslink 门管互链,如已接线)";`--write` 首次确认(无先前记录)时打印该对的双向互链形态提示,用该对的实际文件名(对侧名取记录的 counterpart 字段),可复制、与项目命名约定无关;再确认不重复;`--explain` 增"互链不属于配对契约(规则 7=三件套),本验证器只判存在+摘要"一段。不执法:互链检查不进 verify-pairing(D70——未成文的扩展不该悄悄变红存量配对)。

## Alternatives considered

(a) 收编互链检查被否:规则 7 的契约不含互链,govrail 文档的行 2 互链是实践不是成文约定;收编使存量无互链配对一夜变红,与自建 crosslink 门的采用方重复执法;(c) 只修文档被否:沉默绿的问题在输出语义,不在文档可达性。提示曾考虑放进失败路径——失败路径在采用方的门里,govrail 够不到;放 --write 的作者时刻是本命令拥有的最近的教学位。
