import pika
import json
from typing import Dict, Any, Callable

class MQClient:
    def __init__(self, host: str, queue_name: str):
        self.host = host
        self.queue_name = queue_name
        try:
            # 建立阻塞连接
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
            self.channel = self.connection.channel()
            # 声明队列（持久化，保证 RabbitMQ 重启消息不丢）
            self.channel.queue_declare(queue=queue_name, durable=True)
        except Exception as e:
            raise RuntimeError(f"无法连接到 RabbitMQ: {e}")
        
    def publish_task(self, task: Dict[str, Any]):
        """
        发布任务到队列, task 必须是可序列化字典
        """
        try:
            # 转换为 JSON 字符串
            message = json.dumps(task)
            # 发布消息（持久化，确保消息不丢失）
            self.channel.basic_publish(
                exchange='',                # 使用默认交换机
                routing_key=self.queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 消息持久化
                )
            )
            print(f"已发布任务到队列: {self.queue_name}")
        except Exception as e:
            print(f"发布任务到队列失败: {e}")

    def consume_tasks(self, callback: Callable[[Dict[str, Any]], None]):
        """
        从队列消费任务, 并调用回调函数处理
        """
        def _on_message(ch, method, properties, body):
            """
            处理消息的回调函数
            """
            try:
                # 解析 JSON 消息
                task = json.loads(body)
                # 调用回调函数处理任务
                callback(task)
                # 手动确认消息已处理（ACK）
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f"处理消息失败: {e}")
                # 处理失败时可以选择拒绝消息（NACK）或重新入队
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self.channel.basic_qos(prefetch_count=1)    # 每次只处理一条消息; 公平分发，避免某个 worker 压力过大
        # 开始消费消息
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=_on_message
        )
        print(f"开始消费队列: {self.queue_name}")
        self.channel.start_consuming()

    def close(self):
        """
        关闭连接
        """
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("已关闭 RabbitMQ 连接")