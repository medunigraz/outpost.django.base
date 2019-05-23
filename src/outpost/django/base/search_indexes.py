from haystack import indexes


class StopwordEdgeNgramField(indexes.EdgeNgramField):
    stopwords = [
        'für'
    ]

    def prepare(self, obj):
        data = super().prepare(obj)
        return ' '.join([w for w in data.split() if w not in self.stopwords])
