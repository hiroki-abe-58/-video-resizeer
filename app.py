#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
動画圧縮CLIツール - 音質優先版
"""

__version__ = "1.2.0"

import os
import sys
import subprocess
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple


class VideoCompressor:
    """動画圧縮を管理するクラス"""
    
    # サポートする動画形式
    SUPPORTED_FORMATS = [
        '.mp4', '.avi', '.mov', '.mkv', '.flv', 
        '.wmv', '.webm', '.m4v', '.mpeg', '.mpg'
    ]
    
    # 変換可能な拡張子
    CONVERT_FORMATS = {
        '1': ('mp4', 'MP4 (H.264)'),
        '2': ('mov', 'MOV (QuickTime)'),
        '3': ('avi', 'AVI'),
        '4': ('mkv', 'MKV (Matroska)'),
        '5': ('webm', 'WebM'),
        '6': ('flv', 'FLV (Flash Video)'),
    }
    
    def __init__(self, dry_run: bool = False):
        self.input_files: List[Path] = []
        self.target_size_mb: Optional[float] = None
        self.output_format: Optional[str] = None
        self.batch_mode: bool = False
        self.dry_run: bool = dry_run
    
    def check_ffmpeg(self) -> bool:
        """ffmpegがインストールされているか確認"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_video_files_from_directory(self, directory: Path) -> List[Path]:
        """ディレクトリ内の全動画ファイルを取得"""
        video_files = []
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                video_files.append(file_path)
        return sorted(video_files)
    
    def get_video_info(self, video_path: Path) -> dict:
        """ffprobeで動画情報を取得"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"動画情報の取得に失敗したわ: {e}")
        except json.JSONDecodeError:
            raise RuntimeError("動画情報のパースに失敗。ファイルが壊れてるかも")
    
    def get_file_size_mb(self, file_path: Path) -> float:
        """ファイルサイズをMB単位で取得"""
        size_bytes = file_path.stat().st_size
        return size_bytes / (1024 * 1024)
    
    def calculate_bitrate(self, target_size_mb: float, duration: float, audio_bitrate: int = 192) -> int:
        """目標ファイルサイズから必要なビデオビットレートを計算"""
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        audio_bitrate_bps = audio_bitrate * 1000
        audio_total_bits = audio_bitrate_bps * duration
        video_total_bits = target_size_bits - audio_total_bits
        
        if video_total_bits <= 0:
            raise ValueError("目標サイズが小さすぎる。音声だけで容量オーバーするわ")
        
        video_bitrate_bps = video_total_bits / duration
        return int(video_bitrate_bps / 1000 * 0.95)
    
    def estimate_quality_level(self, video_bitrate: int, video_info: dict) -> str:
        """ビットレートから予想画質レベルを判定"""
        # 動画ストリームを取得
        video_stream = None
        for stream in video_info.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if not video_stream:
            return "不明"
        
        # 解像度取得
        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        
        # 解像度ベースの推奨ビットレート(kbps)
        # 参考: https://support.google.com/youtube/answer/1722171
        if height >= 2160:  # 4K
            excellent = 35000
            good = 20000
            acceptable = 13000
        elif height >= 1440:  # 2K
            excellent = 16000
            good = 10000
            acceptable = 6000
        elif height >= 1080:  # Full HD
            excellent = 8000
            good = 5000
            acceptable = 3000
        elif height >= 720:  # HD
            excellent = 5000
            good = 2500
            acceptable = 1500
        elif height >= 480:  # SD
            excellent = 2500
            good = 1000
            acceptable = 500
        else:
            excellent = 1000
            good = 500
            acceptable = 250
        
        # 判定
        if video_bitrate >= excellent:
            return "🌟 最高画質 (ほぼ劣化なし)"
        elif video_bitrate >= good:
            return "✨ 高画質 (軽微な劣化)"
        elif video_bitrate >= acceptable:
            return "👌 標準画質 (許容範囲)"
        else:
            return "⚠️  低画質 (明らかに劣化)"
    
    def compress_video(self, input_path: Path, output_path: Path, video_bitrate: int, 
                      video_info: dict, current: int = 1, total: int = 1, audio_bitrate: int = 192):
        """動画を圧縮(2パスエンコーディング)"""
        
        if total > 1:
            print(f"\n🎬 [{current}/{total}] {input_path.name} を圧縮中...")
        else:
            print(f"\n🎬 圧縮中です...")
        print("=" * 60)
        
        # 1パス目
        print("\n[1/2] 1パス目: ビットレート解析中...")
        pass1_cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-c:v', 'libx264',
            '-b:v', f'{video_bitrate}k',
            '-pass', '1',
            '-an',
            '-f', 'null',
            '-y',
            '/dev/null' if sys.platform != 'win32' else 'NUL'
        ]
        
        try:
            self._run_ffmpeg_with_progress(pass1_cmd, "1パス目", video_info)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"1パス目のエンコードに失敗: {e}")
        
        # 2パス目
        print("\n[2/2] 2パス目: 最終エンコード中...")
        pass2_cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-c:v', 'libx264',
            '-b:v', f'{video_bitrate}k',
            '-pass', '2',
            '-c:a', 'aac',
            '-b:a', f'{audio_bitrate}k',
            '-y',
            str(output_path)
        ]
        
        try:
            self._run_ffmpeg_with_progress(pass2_cmd, "2パス目", video_info)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"2パス目のエンコードに失敗: {e}")
        
        self._cleanup_ffmpeg_logs()
    
    def _run_ffmpeg_with_progress(self, cmd: list, phase: str, video_info: dict):
        """ffmpegを実行し、進捗を表示"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        duration = float(video_info['format']['duration'])
        
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
            if time_match:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = min(100, (current_time / duration) * 100)
                
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                if progress > 0:
                    elapsed = current_time
                    total_estimated = (elapsed / progress) * 100
                    remaining = total_estimated - elapsed
                    remaining_str = self._format_time(remaining)
                else:
                    remaining_str = "計算中..."
                
                print(f'\r{phase}: [{bar}] {progress:5.1f}% | 残り時間: {remaining_str}', end='', flush=True)
        
        print()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
    
    def _format_time(self, seconds: float) -> str:
        """秒を 'HH:MM:SS' 形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _cleanup_ffmpeg_logs(self):
        """ffmpegの2パスエンコードで生成されるログファイルを削除"""
        log_files = ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']
        for log_file in log_files:
            try:
                if os.path.exists(log_file):
                    os.remove(log_file)
            except Exception:
                pass
    
    def run(self):
        """メイン処理"""
        # フェーズ1: ファイル/ディレクトリパス入力
        self.input_files = self._phase1_get_input_files()
        
        # バッチモード判定
        self.batch_mode = len(self.input_files) > 1
        
        if self.batch_mode:
            self._run_batch_mode()
        else:
            self._run_single_mode()
    
    def _run_single_mode(self):
        """単体ファイルモード"""
        input_path = self.input_files[0]
        video_info = self.get_video_info(input_path)
        
        # フェーズ2: 目標サイズ入力
        target_size_mb = self._phase2_get_target_size(input_path, video_info)
        
        # フェーズ3: 拡張子変換
        output_format = self._phase3_convert_format(input_path)
        
        # フェーズ4 & 5: 圧縮実行 or ドライラン
        if self.dry_run:
            self._dry_run_report(input_path, target_size_mb, output_format, video_info)
        else:
            self._compress_and_report(input_path, target_size_mb, output_format, video_info)
    
    def _run_batch_mode(self):
        """バッチ処理モード"""
        print(f"\n📁 {len(self.input_files)}個の動画ファイルが見つかりました:")
        for i, file_path in enumerate(self.input_files, 1):
            size_mb = self.get_file_size_mb(file_path)
            print(f"  {i}. {file_path.name} ({size_mb:.2f} MB)")
        
        # 一括設定 or 個別設定
        print("\n設定方法を選択してください:")
        print("  1. 一括設定 (全てのファイルに同じ設定を適用)")
        print("  2. 個別設定 (ファイルごとに設定)")
        
        while True:
            choice = input("番号を選択: ").strip()
            if choice in ['1', '2']:
                break
            print("❌ エラー: 1 または 2 を入力してください。")
        
        if choice == '1':
            self._batch_mode_uniform()
        else:
            self._batch_mode_individual()
    
    def _batch_mode_uniform(self):
        """一括設定モード"""
        print("\n【一括設定モード】")
        print("全てのファイルに同じ設定を適用します。")
        
        # 目標サイズ(MB)
        while True:
            try:
                target_size_str = input("\n各ファイルを何MBまで圧縮しますか？: ").strip()
                target_size_mb = float(target_size_str)
                if target_size_mb <= 0:
                    print("❌ エラー: 0より大きい値を入力してください。")
                    continue
                break
            except ValueError:
                print("❌ エラー: 数字を入力してください。")
        
        # 拡張子変換
        print("\n全てのファイルの拡張子を変換しますか？")
        convert = input("(y/何も入力せずEnter): ").strip().lower()
        
        if convert == 'y':
            print("\n変換可能な形式:")
            for key, (ext, desc) in self.CONVERT_FORMATS.items():
                print(f"  {key}. {desc}")
            
            while True:
                format_choice = input("番号を選択: ").strip()
                if format_choice in self.CONVERT_FORMATS:
                    output_format = self.CONVERT_FORMATS[format_choice][0]
                    break
                print("❌ エラー: 正しい番号を入力してください。")
        else:
            output_format = None
        
        # 全ファイルを処理
        total = len(self.input_files)
        for i, input_path in enumerate(self.input_files, 1):
            try:
                video_info = self.get_video_info(input_path)
                current_format = output_format if output_format else input_path.suffix[1:]
                
                if self.dry_run:
                    self._dry_run_report(input_path, target_size_mb, current_format, 
                                        video_info, current=i, total=total)
                else:
                    self._compress_and_report(input_path, target_size_mb, current_format, 
                                            video_info, current=i, total=total)
            except Exception as e:
                print(f"\n❌ エラー: {input_path.name} の処理に失敗: {e}")
                if not self.dry_run:
                    continue_choice = input("続けますか？ (y/n): ").strip().lower()
                    if continue_choice != 'y':
                        break
        
        if self.dry_run:
            print(f"\n✅ ドライラン完了! {total}個のファイルをシミュレートしました。")
        else:
            print(f"\n🎉 バッチ処理完了! {total}個のファイルを処理しました。")
    
    def _batch_mode_individual(self):
        """個別設定モード"""
        print("\n【個別設定モード】")
        
        total = len(self.input_files)
        for i, input_path in enumerate(self.input_files, 1):
            try:
                print(f"\n{'='*60}")
                print(f"[{i}/{total}] {input_path.name}")
                print('='*60)
                
                video_info = self.get_video_info(input_path)
                
                # スキップオプション
                skip = input("このファイルをスキップしますか？ (y/n): ").strip().lower()
                if skip == 'y':
                    print("⏭️  スキップしました。")
                    continue
                
                # 目標サイズ入力
                target_size_mb = self._phase2_get_target_size(input_path, video_info)
                
                # 拡張子変換
                output_format = self._phase3_convert_format(input_path)
                
                # 圧縮実行 or ドライラン
                if self.dry_run:
                    self._dry_run_report(input_path, target_size_mb, output_format, 
                                        video_info, current=i, total=total)
                else:
                    self._compress_and_report(input_path, target_size_mb, output_format, 
                                            video_info, current=i, total=total)
                
            except Exception as e:
                print(f"\n❌ エラー: {input_path.name} の処理に失敗: {e}")
                if not self.dry_run:
                    continue_choice = input("続けますか？ (y/n): ").strip().lower()
                    if continue_choice != 'y':
                        break
        
        if self.dry_run:
            print(f"\n✅ ドライラン完了! {total}個のファイルをシミュレートしました。")
        else:
            print(f"\n🎉 バッチ処理完了! {total}個のファイルを処理しました。")
    
    def _dry_run_report(self, input_path: Path, target_size_mb: float, 
                       output_format: str, video_info: dict, 
                       current: int = 1, total: int = 1):
        """ドライラン結果レポート"""
        current_size = self.get_file_size_mb(input_path)
        duration = float(video_info['format']['duration'])
        
        # ビットレート計算
        try:
            video_bitrate = self.calculate_bitrate(target_size_mb, duration)
        except ValueError as e:
            print(f"\n❌ エラー: {e}")
            return
        
        # 画質推定
        quality_level = self.estimate_quality_level(video_bitrate, video_info)
        
        # 圧縮率計算
        compression_ratio = (1 - target_size_mb / current_size) * 100
        
        # 出力ファイル名生成
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        stem = input_path.stem
        output_name = f"{stem}--compressed--{target_size_mb:.1f}MB--{timestamp}.{output_format}"
        
        # レポート出力
        if total > 1:
            print(f"\n📋 [{current}/{total}] ドライラン結果: {input_path.name}")
        else:
            print(f"\n📋 ドライラン結果")
        print("=" * 60)
        print(f"入力ファイル: {input_path.name}")
        print(f"現在のサイズ: {current_size:.2f} MB")
        print(f"目標サイズ: {target_size_mb:.2f} MB")
        print(f"圧縮率: {compression_ratio:.1f}%")
        print(f"動画の長さ: {self._format_time(duration)}")
        print()
        print("【エンコード設定】")
        print(f"  ビデオビットレート: {video_bitrate} kbps")
        print(f"  音声ビットレート: 192 kbps (AAC)")
        print(f"  コーデック: H.264 (libx264)")
        print()
        print("【予想画質】")
        print(f"  {quality_level}")
        print()
        print("【出力ファイル】")
        print(f"  ファイル名: {output_name}")
        print(f"  保存先: {input_path.parent / output_name}")
        print("=" * 60)
        
        if total == 1:
            print("\n💡 実際に圧縮する場合は --dry-run オプションを外して実行してください。")
    
    def _compress_and_report(self, input_path: Path, target_size_mb: float, 
                            output_format: str, video_info: dict, 
                            current: int = 1, total: int = 1):
        """圧縮実行と結果レポート"""
        duration = float(video_info['format']['duration'])
        
        # ビットレート計算
        try:
            video_bitrate = self.calculate_bitrate(target_size_mb, duration)
            if total == 1:
                print(f"\n📊 計算結果:")
                print(f"  動画ビットレート: {video_bitrate} kbps")
                print(f"  音声ビットレート: 192 kbps (音質優先)")
        except ValueError as e:
            raise RuntimeError(f"ビットレート計算エラー: {e}")
        
        # 出力ファイル名生成
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        stem = input_path.stem
        output_name = f"{stem}--compressed--{target_size_mb:.1f}MB--{timestamp}.{output_format}"
        output_path = input_path.parent / output_name
        
        # 圧縮実行
        self.compress_video(input_path, output_path, video_bitrate, video_info, current, total)
        
        # 完了レポート
        final_size = self.get_file_size_mb(output_path)
        print("\n" + "=" * 60)
        print("✅ 圧縮が完了し、圧縮した動画ファイルは保存されました!")
        print("=" * 60)
        print(f"ファイル名: {output_name}")
        print(f"保存先: {output_path}")
        print(f"目標サイズ: {target_size_mb:.2f} MB")
        print(f"実際のサイズ: {final_size:.2f} MB")
        print(f"差分: {abs(final_size - target_size_mb):.2f} MB")
        print("=" * 60)
    
    def _phase1_get_input_files(self) -> List[Path]:
        """フェーズ1: ファイル/ディレクトリパス取得"""
        print("\n【フェーズ1】")
        while True:
            path_str = input("動画ファイルまたはディレクトリのパスを入力し、エンターを押してください:\n> ").strip()
            path_str = path_str.strip("'\"")
            path = Path(path_str).expanduser()
            
            if not path.exists():
                print(f"❌ エラー: 存在しないパスです。正しいパスを入力してください。")
                continue
            
            # ディレクトリの場合
            if path.is_dir():
                video_files = self.get_video_files_from_directory(path)
                if not video_files:
                    print(f"❌ エラー: このディレクトリには動画ファイルが見つかりませんでした。")
                    print(f"サポート形式: {', '.join(self.SUPPORTED_FORMATS)}")
                    continue
                return video_files
            
            # ファイルの場合
            if not path.is_file():
                print(f"❌ エラー: ファイルまたはディレクトリを指定してください。")
                continue
            
            if path.suffix.lower() not in self.SUPPORTED_FORMATS:
                print(f"❌ エラー: サポートされていない形式です。")
                print(f"サポート形式: {', '.join(self.SUPPORTED_FORMATS)}")
                continue
            
            return [path]
    
    def _phase2_get_target_size(self, input_path: Path, video_info: dict) -> float:
        """フェーズ2: 目標サイズ入力"""
        current_size = self.get_file_size_mb(input_path)
        duration = float(video_info['format']['duration'])
        
        print("\n【フェーズ2】")
        print(f"ファイル名: {input_path.name}")
        print(f"現在のファイル容量: {current_size:.2f} MB")
        print(f"動画の長さ: {self._format_time(duration)}")
        
        while True:
            try:
                target_str = input("\nこの動画を何MBまで圧縮しますか？数字を入力しエンターを押してください。(小数点可):\n> ").strip()
                target_size = float(target_str)
                
                if target_size <= 0:
                    print("❌ エラー: 0より大きい値を入力してください。")
                    continue
                
                if target_size >= current_size:
                    print(f"❌ エラー: 目標サイズ({target_size:.2f}MB)が現在のサイズ({current_size:.2f}MB)以上です。")
                    print("圧縮する意味ないで。もっと小さい値を入力してくれ。")
                    continue
                
                audio_size_mb = (192 * 1000 * duration) / (8 * 1024 * 1024)
                if target_size < audio_size_mb * 1.1:
                    print(f"⚠️  警告: 目標サイズが小さすぎる可能性があります。")
                    print(f"音声ビットレート192kbpsだけで約{audio_size_mb:.2f}MBになります。")
                    confirm = input("それでも続けますか？ (y/n): ").strip().lower()
                    if confirm != 'y':
                        continue
                
                return target_size
                
            except ValueError:
                print("❌ エラー: 数字を入力してください。")
    
    def _phase3_convert_format(self, input_path: Path) -> str:
        """フェーズ3: 拡張子変換"""
        print("\n【フェーズ3】")
        convert = input("拡張子は変換しますか？ (y/何も入力せずEnter): ").strip().lower()
        
        if convert == 'y':
            print("\n変換可能な形式:")
            for key, (ext, desc) in self.CONVERT_FORMATS.items():
                print(f"  {key}. {desc}")
            
            while True:
                choice = input("\n番号を選択してください: ").strip()
                if choice in self.CONVERT_FORMATS:
                    return self.CONVERT_FORMATS[choice][0]
                print("❌ エラー: 正しい番号を入力してください。")
        else:
            return input_path.suffix[1:]
    
    def reset(self):
        """次の圧縮のために変数をリセット"""
        self.input_files = []
        self.target_size_mb = None
        self.output_format = None
        self.batch_mode = False


def main():
    """エントリーポイント"""
    # コマンドライン引数解析
    dry_run = False
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--version', '-v']:
            print(f"動画圧縮ツール v{__version__}")
            sys.exit(0)
        elif sys.argv[1] in ['--dry-run', '-d']:
            dry_run = True
            print("🔍 ドライランモード: 実際の圧縮は行わず、計算結果のみ表示します。")
        elif sys.argv[1] in ['--help', '-h']:
            print("動画圧縮ツール - 使い方")
            print()
            print("使用法:")
            print("  ./compress_video.py              通常モード")
            print("  ./compress_video.py --dry-run    ドライランモード")
            print("  ./compress_video.py --version    バージョン表示")
            print("  ./compress_video.py --help       ヘルプ表示")
            print()
            print("オプション:")
            print("  --dry-run, -d    実際の圧縮を行わず、計算結果のみ表示")
            print("  --version, -v    バージョン情報を表示")
            print("  --help, -h       このヘルプを表示")
            sys.exit(0)
    
    try:
        print("=" * 60)
        print("🎥 動画圧縮ツール - 音質優先版")
        print("=" * 60)
        
        compressor = VideoCompressor(dry_run=dry_run)
        
        if not compressor.check_ffmpeg():
            print("\n❌ エラー: ffmpegがインストールされてないわ")
            print("以下のコマンドでインストールしてくれ:")
            print("  brew install ffmpeg")
            sys.exit(1)
        
        while True:
            compressor.run()
            
            print("\n" + "=" * 60)
            if dry_run:
                continue_choice = input("もう1本シミュレートする？ (y/n): ").strip().lower()
            else:
                continue_choice = input("もう1本圧縮する？ (y/n): ").strip().lower()
            
            if continue_choice != 'y':
                print("\n👋 お疲れさん!またな!")
                break
            
            compressor.reset()
            print("\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  処理が中断されました。")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌予期しないエラーが発生: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
