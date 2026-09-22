# `global-metadata.dat` 翻译数据

这里保存 Unity IL2CPP `global-metadata.dat` 中导出的日文候选字符串，供 Android 和 iOS 版本翻译共用。JSON 使用 UTF-8 编码，字符串索引与原始 metadata 保持一致。

## 目录结构

```text
metadata/
├─ android/
│  ├─ japanese-strings.json
│  ├─ japanese-kana-only.json
│  ├─ japanese-strings.zh-CN.json
│  └─ metadata-info.json
└─ ios/
   ├─ japanese-strings.json
   ├─ japanese-kana-only.json
   ├─ japanese-strings.zh-CN.json
   └─ metadata-info.json
```

- `japanese-strings.json`：含假名或汉字的日文候选，共 2,130 条。
- `japanese-kana-only.json`：只含平假名、片假名的候选，共 1,743 条。
- `japanese-strings.zh-CN.json`：已填写的简体中文翻译；空白项表示暂未翻译或为避免重复键而保留原文。
- `metadata-info.json`：导出时的 metadata 版本、文件大小和字符串总数。

`japanese-strings.json` 中每项的格式如下：

```json
{
  "nth": 123,
  "source": "日文原文",
  "translation": ""
}
```

翻译时只填写 `translation`。不要修改 `nth` 和 `source`；留空的 `translation` 会被脚本跳过。

## 使用脚本

脚本为 `masterdata/metadata_localize.py`。如果在其他电脑使用，请把脚本复制过去，或将下面的 `$Script` 改成脚本的实际路径。首次使用需要安装 Meta String Editor 的 Python 绑定：

```powershell
pip install metastringedit
```

### 导出 Android 或 iOS metadata

先从 APK/IPA 解包，找到以下文件：

- Android：`assets/bin/Data/Managed/Metadata/global-metadata.dat`
- iOS：`Payload/<应用名>.app/Data/Managed/Metadata/global-metadata.dat`

然后执行：

```powershell
$Script = "E:\Ymst\translate\repo\masterdata\metadata_localize.py"

# Android
python $Script export "path\to\android\global-metadata.dat" --out-dir ".\android"

# iOS
python $Script export "path\to\ios\global-metadata.dat" --out-dir ".\ios"
```

导出目录会生成：

- `all-strings.json`：全部字符串。
- `japanese-strings.json`：默认日文翻译模板。
- `japanese-kana-only.json`：排除纯汉字候选的模板。
- `metadata-info.json`：metadata 信息。

纯汉字可能同时属于中文和日文。不能确定时，使用 `japanese-kana-only.json`，或人工检查 `japanese-strings.json` 中的 387 条纯汉字候选。

### 写回翻译

翻译完成后，将翻译模板写回新的 metadata 文件：

当前仓库中的 iOS 中文文件已经按 `source` 原文合并了 Android 的可用翻译；回写 iOS 时使用下面的 `japanese-strings.zh-CN.json`，不要使用未翻译的 `japanese-strings.json`。

```powershell
python $Script apply `
  "path\to\original\global-metadata.dat" `
  ".\ios\japanese-strings.zh-CN.json" `
  ".\ios\global-metadata.translated.dat"
```

脚本默认检查 `source` 是否与当前 metadata 完全匹配，避免把不同版本的翻译写错文件。输出文件必须使用新文件名，原始 metadata 不会被覆盖。

脚本还会检查回写后的字符串值是否重复。若翻译使不同索引变成同一个字符串，脚本会在保存前拒绝输出，避免客户端启动时发生重复键异常。

写回后，将新的 `global-metadata.translated.dat` 放回解包后的 APK/IPA 对应目录，再自行重打包和签名。脚本不负责 APK/IPA 的重打包或签名。

## 当前数据快照

| 平台 | Metadata 版本 | 文件大小 | 字符串总数 | 日文候选 | 假名候选 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Android | 31 | 28,424,920 bytes | 29,620 | 2,130 | 1,743 |
| iOS | 31 | 28,429,112 bytes | 29,424 | 2,130 | 1,743 |

## 翻译注意事项

- 保留 `<color>...</color>`、`<size>...</size>` 等 Unity 富文本标签。
- 保留 `{0}`、`{1}`、`%s` 等占位符。
- 保留原有换行和必要的转义字符。
- Android 和 iOS 必须使用各自对应版本的 metadata 与 JSON，不要交叉套用。
- iOS 的 `japanese-strings.zh-CN.json` 是按 `source` 原文合并生成的，使用 iOS 自己的 `nth` 索引，不能直接把 Android 的索引写入 iOS metadata。
- 翻译完成后建议先用 Meta String Editor 或脚本重新读取几个索引确认，再进行打包测试。
