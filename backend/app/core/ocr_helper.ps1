param(
    [Parameter(Mandatory=$true)]
    [string]$ImagePath
)

$ErrorActionPreference = "Stop"

try {
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.FileAccessMode, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.IRandomAccessStream, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    $asTaskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    }

    function Await-Async($winRtOp, $type) {
        $method = $asTaskMethod.MakeGenericMethod($type)
        $task = $method.Invoke($null, @($winRtOp))
        $task.Wait()
        return $task.Result
    }

    $resolvedPath = (Resolve-Path $ImagePath).Path
    $fileOp = [Windows.Storage.StorageFile]::GetFileFromPathAsync($resolvedPath)
    $file = Await-Async $fileOp ([Windows.Storage.StorageFile])

    $streamOp = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    $stream = Await-Async $streamOp ([Windows.Storage.Streams.IRandomAccessStream])

    $decoderOp = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = Await-Async $decoderOp ([Windows.Graphics.Imaging.BitmapDecoder])

    $bitmapOp = $decoder.GetSoftwareBitmapAsync()
    $bitmap = Await-Async $bitmapOp ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) {
        $lang = [Windows.Globalization.Language]::new("en-US")
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    }

    $ocrOp = $engine.RecognizeAsync($bitmap)
    $result = Await-Async $ocrOp ([Windows.Media.Ocr.OcrResult])

    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    if ($result -and $result.Text) {
        [Console]::WriteLine($result.Text)
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.ToString())
    exit 1
}
