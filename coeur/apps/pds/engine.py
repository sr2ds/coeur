from datetime import datetime
import json

from coeur.apps.ssg.db import DatabaseManager
from coeur.apps.pds.channels import channel_engines, Channels


class Engine:
    def __init__(
        self,
        channels: list[Channels],
        total: int,
    ):
        self.channels = channels
        self.total = total

    def run(self) -> None:
        for channel in self.channels:
            # when more channels be avaiable, we can to run them in parallel
            self.publish(channel)

    def publish(self, channel: Channels) -> None:
        db = DatabaseManager()
        posts_without_channel_url = db.get_posts(
            limit=self.total,
            filters=[
                {"extra": f'"{channel.value}": {{'},
            ],
        )

        channel_engine = channel_engines[channel]()
        for post in posts_without_channel_url:
            try:
                published_url = channel_engine.publish(post)
                post.extra = self.handle_extra(channel, post, published_url)
                db.session.merge(post)
                db.session.commit()
            except Exception as e:
                print(e)
                db.session.rollback()

        db.session.close()

    def handle_extra(self, channel: Channels, post, published_url: str) -> str:
        try:
            channel_object = {
                "url": published_url,
                "date": datetime.now().isoformat(),
            }
            extra = json.loads(post.extra)
            if "social" in extra:
                extra["social"][channel.value] = channel_object
            else:
                extra["social"] = {channel.value: channel_object}
            return json.dumps(extra)
        except:
            print("Error when try to handle the extra post json", post.title)
            return post.extra
