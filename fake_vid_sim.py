#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fake_vid_sim.py
- 输入一个视频源 URL（文件/rtsp/usb）
- 指定多个 MQTT topics
- 指定数据格式类型：inference_result / raw_frames
- 将帧以 RAW 或 JPEG 编码后用相应的 Protobuf 封装，再发布到所有 topic

依赖：
- OpenCV (cv2)
- 你的 pyengine 包（含 MqttBus、logger、protobufs、StreamReader）
"""

import os
import cv2
import time
import signal
import argparse
from typing import List, Dict, Any, Optional

from pyengine.utils.logger import logger
from pyengine.io.network.mqtt_bus import MqttBus
from pyengine.io.streamer.stream_reader import StreamReader
from pyengine.io.network.protobufs import import_inference_result, import_rawframe


def _encode_frame_bytes(frame, encode: str, jpeg_quality: int) -> bytes:
    """
    根据 encode 产出 frame_raw_data:
      - 'raw'  : 直接 frame.tobytes()
      - 'jpeg' : cv2.imencode('.jpg', frame, [IMWRITE_JPEG_QUALITY, jpeg_quality])
    """
    if encode == "raw":
        return frame.tobytes()
    # jpeg
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


def make_inference_result_packer(pb2_dir: str,
                                 encode: str = "raw",
                                 jpeg_quality: int = 85,
                                 results_bytes_func: Optional[callable] = None):
    """
    返回 pack(frame, meta) -> bytes
    - encode = 'raw'  : frame_raw_data = 未压缩像素 (H*W*C)
    - encode = 'jpeg' : frame_raw_data = JPEG 字节
    - inference_results:
        * 如果 results_bytes_func 不为 None：用其返回的 bytes
        * 否则为空字节 b""
    """
    InferenceResult = import_inference_result(pb2_dir)

    def pack(frame, meta: Dict[str, Any]) -> bytes:
        h, w = frame.shape[:2]
        c = frame.shape[2] if len(frame.shape) == 3 else 1

        msg = InferenceResult()
        msg.frame_width = int(meta.get("width",  w))
        msg.frame_height = int(meta.get("height", h))
        msg.frame_channels = int(c)
        msg.frame_raw_data = _encode_frame_bytes(frame, encode=encode, jpeg_quality=jpeg_quality)

        if results_bytes_func is not None:
            rb = results_bytes_func(frame, meta)
            if not isinstance(rb, (bytes, bytearray, memoryview)):
                raise TypeError("results_bytes_func must return bytes")
            msg.inference_results = bytes(rb)
        else:
            msg.inference_results = b""

        return msg.SerializeToString()

    return pack


def make_rawframe_packer(pb2_dir: str, encode: str = "raw", jpeg_quality: int = 85):
    """
    返回 pack(frame, meta) -> bytes
    - RawFrame: 仅包含 width/height/channels 和 frame_raw_data
    - encode = 'raw'  : 未压缩像素
      encode = 'jpeg' : JPEG 字节
    """
    RawFrame = import_rawframe(pb2_dir)

    def pack(frame, meta: Dict[str, Any]) -> bytes:
        h, w = frame.shape[:2]
        c = frame.shape[2] if len(frame.shape) == 3 else 1

        msg = RawFrame()
        msg.frame_width = int(meta.get("width",  w))
        msg.frame_height = int(meta.get("height", h))
        msg.frame_channels = int(c)
        msg.frame_raw_data = _encode_frame_bytes(frame, encode=encode, jpeg_quality=jpeg_quality)
        return msg.SerializeToString()

    return pack


def parse_topics(arg_topics: str) -> List[str]:
    """支持逗号分隔；去重并保持顺序"""
    if not arg_topics:
        return []
    items = [t.strip() for t in arg_topics.split(",") if t.strip()]
    seen, result = set(), []
    for t in items:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def main():
    parser = argparse.ArgumentParser(description="Fake video simulator: publish frames to MQTT topics.")
    parser.add_argument("--url", required=True, help="视频源：文件/RTSP/HTTP/USB（如 0/1 表示相机索引）")
    parser.add_argument("--topics", required=True,
                        help="逗号分隔的 topic 列表，例如 'pipelines/p1/inference,magistrates/m1/inference'")
    parser.add_argument("--format", choices=["inference_result", "raw_frames"], default="inference_result",
                        help="发送数据格式类型")
    parser.add_argument("--encode", choices=["raw", "jpeg"], default="raw",
                        help="帧字节编码方式：raw=未压缩像素(与真实检测端一致)，jpeg=压缩字节")
    parser.add_argument("--pb2-dir", default="./protobufs", help="inference_result_pb2.py / raw_frames_pb2.py 所在目录")
    parser.add_argument("--broker-host", default=os.getenv("BROKER_HOST", "127.0.0.1"))
    parser.add_argument("--broker-port", type=int, default=int(os.getenv("BROKER_PORT", "1883")))
    parser.add_argument("--client-id", default=os.getenv("CLIENT_ID", "fake_vid_sim"))
    parser.add_argument("--qos", type=int, default=0)
    parser.add_argument("--retain", action="store_true", help="MQTT retain 标志")
    parser.add_argument("--jpeg-quality", type=int, default=int(os.getenv("JPEG_QUALITY", "85")))
    parser.add_argument("--width", type=int, default=-1, help="输出宽，-1 表示使用源宽")
    parser.add_argument("--height", type=int, default=-1, help="输出高，-1 表示使用源高")
    parser.add_argument("--fps", type=int, default=-1, help="输出 FPS，-1 表示不限帧率（按最快读取）")
    parser.add_argument("--stat-interval", type=float, default=5.0, help="统计打印间隔（秒）")
    args = parser.parse_args()

    topics: List[str] = parse_topics(args.topics)
    if not topics:
        raise SystemExit("必须提供至少一个 topic（--topics）")

    # 组装 packer（两种 format 都支持 raw/jpeg）
    if args.format == "inference_result":
        packer = make_inference_result_packer(args.pb2_dir, encode=args.encode, jpeg_quality=args.jpeg_quality)
    else:
        packer = make_rawframe_packer(args.pb2_dir, encode=args.encode, jpeg_quality=args.jpeg_quality)

    # 初始化 MQTT
    bus = MqttBus(host=args.broker_host, port=args.broker_port, client_id=args.client_id)
    bus.start()
    logger.info("fake_vid_sim", f"MQTT connected to {args.broker_host}:{args.broker_port} as {args.client_id}")

    # 初始化视频读取
    sr = StreamReader(url=args.url, width=args.width, height=args.height, fps=args.fps)
    sr.start()

    sent_frames, last_stat_time = 0, time.time()
    exiting = {"flag": False}

    def _handle_sig(sig, frame):
        exiting["flag"] = True
        logger.info("fake_vid_sim", f"Signal {sig} received, exiting...")

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    try:
        while not exiting["flag"]:
            frame = sr.read_frame()
            if frame is None:
                time.sleep(0.005)
                continue

            h, w = frame.shape[:2]
            meta = {
                "width": w,
                "height": h,
                "ts_unix_ms": int(time.time() * 1000),
                "src_url": args.url,
            }
            try:
                payload = packer(frame, meta)
                for tp in topics:
                    bus.publish(tp, payload, qos=args.qos, retain=args.retain)
                sent_frames += 1
            except Exception as e:
                logger.error("fake_vid_sim", f"failed to pack/publish a frame: {e}")
                time.sleep(0.02)

            now = time.time()
            if now - last_stat_time >= args.stat_interval:
                os.system("cls" if os.name == "nt" else "clear")
                fps = sent_frames / (now - last_stat_time)
                logger.info("fake_vid_sim", f"sent {sent_frames} frames in {now - last_stat_time:.1f}s "
                                            f"→ {fps:.2f} FPS to {len(topics)} topic(s) "
                                            f"[format={args.format}, encode={args.encode}]")
                sent_frames = 0
                last_stat_time = now

    finally:
        try:
            sr.stop()
        except Exception as e:
            logger.warning("fake_vid_sim", f"StreamReader stop() error: {e}")
        try:
            bus.stop()
        except Exception as e:
            logger.warning("fake_vid_sim", f"MqttBus stop() error: {e}")
        logger.info("fake_vid_sim", "Bye.")


if __name__ == "__main__":
    main()
