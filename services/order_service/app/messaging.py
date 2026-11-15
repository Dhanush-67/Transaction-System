import pika
import json

def publish_recovery_job(order_id:int):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )

    channel = connection.channel()

    channel.queue_declare(
        queue="order_recovery",
        durable=True
    )

    channel.basic_publish(
        exchange="",
        routing_key="order_recovery",
        body=json.dumps({"order_id": order_id}),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()  

