from tests.fixtures import evaluation
cases = evaluation.corpus(seeds=(0,))
padded, shifted = [], []
for case in cases:
    for inj in case.record["tampering"]:
        b = inj["box"]
        p = [b[0]-10, b[1]-10, b[2]+10, b[3]+10]
        s = [b[0] + (b[2]-b[0])//2, b[1], b[2], b[3]]
        padded.append(evaluation.iou(b, p))
        shifted.append(evaluation.iou(b, s))
print("padded", [round(v, 4) for v in padded])
print("shifted", [round(v, 4) for v in shifted])
print("mean padded", sum(padded)/len(padded), "mean shifted", sum(shifted)/len(shifted))