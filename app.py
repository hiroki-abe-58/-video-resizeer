#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
動画圧縮CLIツール - 音質優先版
"""

import os
import sys
import subprocess
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple


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
    
    def __init__(self):
        self.input_path: Optional[Path] = None
        self.target_size_mb: Optional[float] = None
        self.output_format: Optional[str] = None
        self.video_info: Optional[dict] = None
    
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
        # 目標サイズ(MB) -> bits
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        
        # 音声ビットレート(kbps) -> bits/sec
        audio_bitrate_bps = audio_bitrate * 1000
        
        # 音声トータルサイズ
        audio_total_bits = audio_bitrate_bps * duration
        
        # ビデオに割り当て可能なサイズ
        video_total_bits = target_size_bits - audio_total_bits
        
        if video_total_bits <= 0:
            raise ValueError("目標サイズが小さすぎる。音声だけで容量オーバーするわ")
        
        # ビデオビットレート(bps)
        video_bitrate_bps = video_total_bits / duration
        
        # kbpsに変換(余裕を持たせて95%にする)
        return int(video_bitrate_bps / 1000 * 0.95)
    
    def compress_video(self, input_path: Path, output_path: Path, video_bitrate: int, audio_bitrate: int = 192):
        """動画を圧縮(2パスエンコーディング)"""
        
        print("\n🎬 圧縮中です...")
        print("=" * 60)
        
        # 1パス目
        print("\n[1/2] 1パス目: ビットレート解析中...")
        pass1_cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-c:v', 'libx264',
            '-b:v', f'{video_bitrate}k',
            '-pass', '1',
            '-an',  # 音声なし
            '-f', 'null',
            '-y',
            '/dev/null' if sys.platform != 'win32' else 'NUL'
        ]
        
        try:
            self._run_ffmpeg_with_progress(pass1_cmd, "1パス目")
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
            self._run_ffmpeg_with_progress(pass2_cmd, "2パス目")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"2パス目のエンコードに失敗: {e}")
        
        # ログファイル削除
        self._cleanup_ffmpeg_logs()
    
    def _run_ffmpeg_with_progress(self, cmd: list, phase: str):
        """ffmpegを実行し、進捗を表示"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        duration = float(self.video_info['format']['duration'])
        
        # 進捗表示用
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            # timeパラメータから進捗を取得
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
            if time_match:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = min(100, (current_time / duration) * 100)
                
                # プログレスバー表示
                bar_length = 40
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                # 残り時間計算
                if progress > 0:
                    elapsed = current_time
                    total_estimated = (elapsed / progress) * 100
                    remaining = total_estimated - elapsed
                    remaining_str = self._format_time(remaining)
                else:
                    remaining_str = "計算中..."
                
                print(f'\r{phase}: [{bar}] {progress:5.1f}% | 残り時間: {remaining_str}', end='', flush=True)
        
        print()  # 改行
        
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
                pass  # ログファイル削除失敗は無視
    
    def run(self):
        """メイン処理"""
        # フェーズ1: ファイルパス入力
        self.input_path = self._phase1_get_file_path()
        
        # 動画情報取得
        self.video_info = self.get_video_info(self.input_path)
        
        # フェーズ2: 目標サイズ入力
        self.target_size_mb = self._phase2_get_target_size()
        
        # フェーズ3: 拡張子変換
        self.output_format = self._phase3_convert_format()
        
        # フェーズ4 & 5: 圧縮実行
        self._phase4_compress()
    
    def reset(self):
        """次の圧縮のために変数をリセット"""
        self.input_path = None
        self.target_size_mb = None
        self.output_format = None
        self.video_info = None
    
    def _phase1_get_file_path(self) -> Path:
        """フェーズ1: 動画ファイルパス取得"""
        print("\n【フェーズ1】")
        while True:
            path_str = input("動画のパスを入力し、エンターを押してください:\n> ").strip()
            
            # クォート除去(ドラッグ&ドロップ対応)
            path_str = path_str.strip("'\"")
            
            path = Path(path_str).expanduser()
            
            if not path.exists():
                print(f"❌ エラー: 存在しないファイルです。正しい動画のパスを入力してください。")
                continue
            
            if not path.is_file():
                print(f"❌ エラー: ディレクトリではなく、ファイルのパスを指定してください。")
                continue
            
            if path.suffix.lower() not in self.SUPPORTED_FORMATS:
                print(f"❌ エラー: サポートされていない形式です。")
                print(f"サポート形式: {', '.join(self.SUPPORTED_FORMATS)}")
                continue
            
            return path
    
    def _phase2_get_target_size(self) -> float:
        """フェーズ2: 目標サイズ入力"""
        current_size = self.get_file_size_mb(self.input_path)
        duration = float(self.video_info['format']['duration'])
        
        print("\n【フェーズ2】")
        print(f"ファイル名: {self.input_path.name}")
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
                
                # 音声だけで目標サイズを超えないかチェック
                audio_size_mb = (192 * 1000 * duration) / (8 * 1024 * 1024)
                if target_size < audio_size_mb * 1.1:  # 10%のマージン
                    print(f"⚠️  警告: 目標サイズが小さすぎる可能性があります。")
                    print(f"音声ビットレート192kbpsだけで約{audio_size_mb:.2f}MBになります。")
                    confirm = input("それでも続けますか？ (y/n): ").strip().lower()
                    if confirm != 'y':
                        continue
                
                return target_size
                
            except ValueError:
                print("❌ エラー: 数字を入力してください。")
    
    def _phase3_convert_format(self) -> str:
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
            return self.input_path.suffix[1:]  # 先頭の'.'を除去
    
    def _phase4_compress(self):
        """フェーズ4 & 5: 圧縮実行"""
        duration = float(self.video_info['format']['duration'])
        
        # ビットレート計算
        try:
            video_bitrate = self.calculate_bitrate(self.target_size_mb, duration)
            print(f"\n📊 計算結果:")
            print(f"  動画ビットレート: {video_bitrate} kbps")
            print(f"  音声ビットレート: 192 kbps (音質優先)")
        except ValueError as e:
            print(f"\n❌ エラー: {e}")
            sys.exit(1)
        
        # 出力ファイル名生成
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        stem = self.input_path.stem
        output_name = f"{stem}--compressed--{self.target_size_mb:.1f}MB--{timestamp}.{self.output_format}"
        output_path = self.input_path.parent / output_name
        
        # 圧縮実行
        try:
            self.compress_video(self.input_path, output_path, video_bitrate)
        except Exception as e:
            print(f"\n❌ エラー: 圧縮に失敗しました: {e}")
            sys.exit(1)
        
        # 完了
        final_size = self.get_file_size_mb(output_path)
        print("\n" + "=" * 60)
        print("✅ 圧縮が完了し、圧縮した動画ファイルは保存されました!")
        print("=" * 60)
        print(f"ファイル名: {output_name}")
        print(f"保存先: {output_path}")
        print(f"目標サイズ: {self.target_size_mb:.2f} MB")
        print(f"実際のサイズ: {final_size:.2f} MB")
        print(f"差分: {abs(final_size - self.target_size_mb):.2f} MB")
        print("=" * 60)


def main():
    """エントリーポイント"""
    try:
        print("=" * 60)
        print("🎥 動画圧縮ツール - 音質優先版")
        print("=" * 60)
        
        compressor = VideoCompressor()
        
        # ffmpegチェック(初回のみ)
        if not compressor.check_ffmpeg():
            print("\n❌ エラー: ffmpegがインストールされてないわ")
            print("以下のコマンドでインストールしてくれ:")
            print("  brew install ffmpeg")
            sys.exit(1)
        
        # 圧縮ループ
        while True:
            # 圧縮実行
            compressor.run()
            
            # 次の動画を圧縮するか確認
            print("\n" + "=" * 60)
            continue_choice = input("もう1本圧縮する？ (y/n): ").strip().lower()
            
            if continue_choice != 'y':
                print("\n👋 お疲れさん!またな!")
                break
            
            # 変数リセット
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
