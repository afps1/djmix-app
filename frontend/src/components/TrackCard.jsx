import WaveformView from './WaveformView.jsx';

export default function TrackCard({
  track, index, cueIn, cueOut,
  onCueInChange, onCueOutChange, onRemove,
  onDragStart, onDragEnd, dragging,
}) {
  const formatTime = (sec) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div
      className={`track-card${dragging ? ' dragging' : ''}`}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', `track:${index}`);
        e.dataTransfer.effectAllowed = 'move';
        onDragStart?.(index);
      }}
      onDragEnd={onDragEnd}
    >
      <div className="track-card-header">
        <div className="track-index">{index + 1}</div>
        <div className="track-name">{track.filename}</div>
        <div className="track-badges">
          <span className="badge badge-bpm">{track.bpm.toFixed(1)} BPM</span>
          {track.camelot && <span className="badge badge-key" title={track.key}>{track.camelot}</span>}
          {track.lufs != null && <span className="badge badge-lufs">{track.lufs.toFixed(1)} LUFS</span>}
          <span className="badge badge-dur">{formatTime(track.duration)}</span>
          <span className="badge badge-ch">{track.channels}ch</span>
        </div>
        <button className="track-remove" onClick={() => onRemove(track.id)} title="Remover">×</button>
      </div>

      <WaveformView
        track={track}
        cueIn={cueIn}
        cueOut={cueOut}
        onCueInChange={onCueInChange}
        onCueOutChange={onCueOutChange}
      />
    </div>
  );
}
