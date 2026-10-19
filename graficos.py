import csv
import matplotlib.pyplot as plt

lista_rtt = []
lista_thoughput = []
lista_seq = []
with open('dados.csv', newline='') as csvfile:
    reader = csv.reader(csvfile, delimiter=',')
    next(reader, None)
    
    seq = 0
    for row in reader:
        lista_seq.append(seq)
        lista_rtt.append(float(row[0]))
        lista_thoughput.append(float(row[1]))
        seq += 1


media_rtt = []
media_thoughput = []
window = 10
for ind in range(len(lista_rtt) - window + 1):
    media_rtt.append(sum(lista_rtt[ind:ind+window])/window)

for ind in range(len(lista_rtt) - window + 1):
    media_thoughput.append(sum(lista_thoughput[ind:ind+window])/window)

plt.subplot(1, 2, 1)
plt.plot(lista_seq[window-1:], media_rtt, label='rtt')
plt.xlabel('Segmento')
plt.ylabel('RTT')
plt.title('rtt')

plt.subplot(1, 2, 2)
plt.plot(lista_seq[window-1:], media_thoughput, label='thoughput')
plt.xlabel('Segmento')
plt.ylabel('thoughput')
plt.title('thoughput')
plt.show()
